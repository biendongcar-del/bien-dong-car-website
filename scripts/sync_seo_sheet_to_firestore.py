#!/usr/bin/env python3
"""One-way SEO Google Sheets -> Firestore draft importer. No automatic publishing."""
import hashlib
import html
import json
import os
import re
import sys
import unicodedata

import gspread
from google.cloud import firestore
from google.oauth2 import service_account

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/datastore",
]
LANGS = {"VI": "vi", "EN": "en", "ZH": "zh", "KO": "ko"}
REQUIRED = {"Từ khóa", "Trạng thái"}
READY_STATUSES = {"Chờ duyệt"}


def slugify(value):
    value = value.lower().replace("đ", "d")
    value = "".join(
        c for c in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(c)
    )
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", value))[:110]


def plain_text(value):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def description(value):
    raw = plain_text(value)
    return raw[:157].rstrip() + "..." if len(raw) > 160 else raw


def main():
    raw = os.environ.get("SEO_SYNC_SERVICE_ACCOUNT", "")
    spreadsheet_id = os.environ.get("SEO_SHEET_ID", "")
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "")
    sheet_tab = os.environ.get("SEO_SHEET_TAB", "Trang tính1")
    if not (raw and spreadsheet_id and project_id):
        raise RuntimeError("Configure SEO_SYNC_SERVICE_ACCOUNT, SEO_SHEET_ID and FIREBASE_PROJECT_ID")
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    sheet = gspread.authorize(creds).open_by_key(spreadsheet_id).worksheet(sheet_tab)
    data = sheet.get_all_values()
    if not data:
        raise RuntimeError("Main SEO sheet is empty")
    headers = [str(h).strip() for h in data[0]]
    if not REQUIRED.issubset(headers):
        raise RuntimeError("Missing required SEO columns: " + repr(REQUIRED - set(headers)))
    if len(headers) != len(set(headers)):
        raise RuntimeError("Duplicate sheet headers found")
    client = firestore.Client(project=project_id, credentials=creds)
    created = updated = unchanged = skipped = 0
    seen = set()

    for rownum, cells in enumerate(data[1:], start=2):
        row = dict(zip(headers, cells + [""] * max(0, len(headers) - len(cells))))
        keyword = row.get("Từ khóa", "").strip()
        if not keyword or row.get("Trạng thái", "").strip() not in READY_STATUSES:
            skipped += 1
            continue
        for suffix, lang in LANGS.items():
            title = row.get("Tiêu đề " + suffix, "").strip()
            content = row.get("Nội dung " + suffix, "").strip()
            if not title or not content:
                continue
            identity = (keyword.casefold(), lang)
            if identity in seen:
                raise RuntimeError("Duplicate keyword/language within sheet, row " + str(rownum))
            seen.add(identity)
            if len(content.encode("utf-8")) > 700_000:
                raise RuntimeError("Article content too large at sheet row " + str(rownum))
            document_id = "seo_" + hashlib.sha256((keyword.casefold() + "|" + lang).encode()).hexdigest()[:36]
            doc_ref = client.collection("articles").document(document_id)
            existing = doc_ref.get()
            if existing.exists:
                old = existing.to_dict() or {}
                if old.get("status") == "published":
                    skipped += 1
                    continue
            else:
                # Reuse existing manually-created article if there is one, to avoid duplicates.
                matches = list(client.collection("articles").where("keyword", "==", keyword).stream())
                matching = [x for x in matches if (x.to_dict() or {}).get("lang", "vi") == lang]
                if matching:
                    if len(matching) > 1:
                        raise RuntimeError("Multiple existing articles for keyword/language; review manually: " + keyword)
                    doc_ref = matching[0].reference
                    old = matching[0].to_dict() or {}
                    if old.get("status") == "published":
                        skipped += 1
                        continue
                    existing = matching[0]
                else:
                    old = {}
            fields = {
                "lang": lang,
                "keyword": keyword,
                "title": title,
                "seoTitle": title[:60],
                "meta": description(content),
                "content": content,
                "slug": slugify(keyword) + ("-" + lang if lang != "vi" else ""),
                "status": "draft",
                "source": "seo-google-sheets",
                "seoQualityScore": int(float(row.get("Điểm chất lượng", "0") or "0")),
            }
            if existing.exists:
                fields["slug"] = old.get("slug") or fields["slug"]
                if all(old.get(k) == v for k, v in fields.items()):
                    unchanged += 1
                    continue
                fields["updatedAt"] = firestore.SERVER_TIMESTAMP
                doc_ref.set(fields, merge=True)
                updated += 1
            else:
                fields.update({
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                    "createdBy": "seo-sync",
                })
                doc_ref.set(fields, merge=True)
                created += 1
    print(f"SEO sync complete: created={created}, updated={updated}, unchanged={unchanged}, skipped={skipped}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("SEO sync failed: " + str(exc), file=sys.stderr)
        sys.exit(1)
