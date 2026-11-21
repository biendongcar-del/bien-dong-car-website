# Tự đồng bộ SEO Google Sheets → Firestore

Hệ thống chạy **mỗi giờ** hoặc thủ công qua GitHub Actions. Đọc sheet SEO chính (`Trang tính1`) và chuyển những hàng có `Trạng thái = Chờ duyệt` thành các bài **draft** trong collection `articles`. Nhập cả bốn ngôn ngữ VI/EN/ZH/KO. Không tự xuất bản.

## Cần cấu hình trước lần chạy đầu
1. Dùng một **Google Cloud service account** được quyền *đọc* bảng Google Sheets SEO chính và quyền ghi collection `articles` vào đúng Firebase/Google Cloud project. Tránh dùng tài khoản chủ sở hữu và chỉ cấp các quyền cần thiết.
2. Vào **GitHub repository → Settings → Secrets and variables → Actions** tạo ba repository secrets:
   - `SEO_SYNC_SERVICE_ACCOUNT`: nội dung JSON service account (không commit lên GitHub).
   - `SEO_SHEET_ID`: ID bảng chính (không phải bảng Cần chỉnh sửa).
   - `FIREBASE_PROJECT_ID`: Project ID của Firebase đang được `admin.html` sử dụng.
3. Chia sẻ bảng SEO chính cho email service account với vai trò Viewer.
4. Mở **Actions → Sync approved-for-review SEO articles to Firestore drafts → Run workflow**, sau đó kiểm tra log và trang quản trị. Chỉ khi kiểm thử đạt mới để lịch tự chạy.

## Quy tắc an toàn
- Chỉ đọc bài `Chờ duyệt`; không xóa hoặc sửa Google Sheets.
- Không thay đổi bài Firestore có `status = published`.
- Đồng bộ lặp lại không tạo bài trùng theo từ khóa/ngôn ngữ; ưu tiên tái sử dụng bản nháp trước đó.
- Nếu nhiều bài Firestore trùng từ khóa/ngôn ngữ, hoặc tiêu đề bảng sai, dừng và báo lỗi thay vì ghi bừa.
- Không cấp quyền ghi Firestore cho JavaScript công khai trên GitHub Pages.
- Đây là đồng bộ Google Sheets → bản nháp Firestore; **chưa phải** tự xuất bản lên website. Nên xác nhận quy tắc duyệt bài trước khi bật tự xuất bản.

## Lưu ý tích hợp
`admin.html` hiện lưu bài trong collection `articles` với các trường `lang,title,slug,keyword,seoTitle,meta,content,status`. Script dùng đúng bộ trường đó để các bản nháp xuất hiện trong trang quản trị. Nếu hiện tại có bài nhập tay có từ khóa khác chính tả, cần rà soát một lần để tránh bài nội dung tương tự.
