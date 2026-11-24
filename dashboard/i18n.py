"""UI strings (Persian is the default language, English is also provided)."""
from __future__ import annotations

import streamlit as st

PAGES = ["overview", "new", "imgproc", "digitize", "explorer", "math", "stats", "viz", "reports", "history"]

STR = {
    "fa": dict(
        app_tagline="تبدیل تصویر نمودار به داده، معادله و گزارش علمی",
        nav_overview="۱. نمای کلی (Overview)", nav_new="۲. تحلیل جدید (New Analysis)", nav_imgproc="۳. پردازش تصویر (Image Processing)",
        nav_digitize="۴. دیجیتالی‌سازی (Chart Digitization)", nav_explorer="۵. داده‌کاوی (Data Explorer)",
        nav_math="۶. تحلیل ریاضی (Mathematical Analysis)", nav_stats="۷. تحلیل آماری (Statistical Analysis)",
        nav_viz="۸. مصورسازی (Visualization)", nav_reports="۹. گزارش‌ها (Reports)", nav_history="۱۰. تاریخچه (Project History)",
        language="زبان / Language", theme_dark="حالت تیره", undo="↩ بازگردانی (Undo)", redo="↪ انجام مجدد (Redo)", active_project="پروژه فعال",
        no_project="پروژه‌ای باز نیست. از «تحلیل جدید» شروع کنید.", created_by="سازنده: حمید یارعلی",
        projects="پروژه‌ها", images_done="تصاویر پردازش‌شده", charts_found="نمودارهای شناسایی‌شده", series_count="سری‌های داده",
        points_count="نقاط استخراج‌شده", fits_count="معادلات برازش‌شده", recent_projects="پروژه‌های اخیر", last_events="آخرین تحلیل‌ها",
        open="باز کردن", copy="کپی", delete="حذف", download="دانلود", upload_files="فایل‌های نمودار (PNG, JPG, TIFF, BMP, WEBP, SVG, PDF)",
        drag_hint="فایل را بکشید و رها کنید یا انتخاب کنید", start_analysis="شروع تحلیل خودکار", settings="تنظیمات استخراج",
        preview="پیش‌نمایش", try_sample="امتحان با نمونه (Sample Data)", sample_note="Sample Data — نمودار مصنوعی با داده مرجع",
        running="در حال پردازش…", cancel_hint="برای لغو، روی هر دکمه‌ی دیگر کلیک کنید (اجرا متوقف می‌شود).", done="تحلیل کامل شد",
        failed="خطا در پردازش", pdf_page="صفحه PDF", original="تصویر اصلی", processed="تصویر پردازش‌شده",
        panel="پنل", plot_area="ناحیه نمودار", calibration="کالیبراسیون محورها", axis_info="عنوان و واحد محورها",
        apply="اعمال", apply_rerun="اعمال و استخراج دوباره", rotation="چرخش دستی (درجه)", scale_type="نوع مقیاس",
        series="سری", select_series="انتخاب سری", rename="تغییر نام", color="رنگ", add_point="افزودن نقطه", delete_points="حذف نقاط",
        apply_edits="اعمال ویرایش‌ها", redigitize="استخراج دوباره با این تنظیمات", n_points="تعداد نقاط", sampling="روش نمونه‌برداری",
        search="جست‌وجو", filter_status="فیلتر وضعیت", columns="ستون‌ها", copy_data="کپی داده‌ها", run_analysis="اجرای تحلیل",
        models="مدل‌ها", compare_models="مقایسه مدل‌ها", equations="معادلات", derivative="مشتق", integral="انتگرال",
        generate="تولید خروجی", language_report="زبان گزارش", formats="فرمت‌های خروجی", download_all="دانلود همه (ZIP)",
        quality="کیفیت استخراج", warnings="هشدارها", ok_saved="ذخیره شد", needs_calib="کالیبراسیون محور ناقص است؛ مقادیر تیک‌ها را وارد کنید.",
        ocr_missing="Tesseract OCR نصب نیست. راهنمای نصب:", approx_note="مدل‌های برازش‌شده فقط تقریبی‌اند، نه قانون واقعی پدیده.",
        not_independent="نقاط متراکم مستقل نیستند؛ مقادیر p معنادار آماری نیستند.", import_zip="بازیابی پروژه از ZIP",
        export_zip="خروجی ZIP پروژه", search_projects="جست‌وجوی پروژه", no_data="داده‌ای وجود ندارد.", chart_type="نوع نمودار",
        override_type="تغییر دستی نوع نمودار", sample_data="داده نمونه", hint_manual="تنظیم دستی", legend_name="نام در Legend",
        undo_done="بازگردانی شد", redo_done="دوباره اعمال شد", nothing_undo="چیزی برای بازگردانی نیست",
    ),
    "en": dict(
        app_tagline="Turn chart images into data, equations and scientific reports",
        nav_overview="1. Overview", nav_new="2. New Analysis", nav_imgproc="3. Image Processing", nav_digitize="4. Chart Digitization",
        nav_explorer="5. Data Explorer", nav_math="6. Mathematical Analysis", nav_stats="7. Statistical Analysis",
        nav_viz="8. Visualization", nav_reports="9. Reports", nav_history="10. Project History",
        language="Language / زبان", theme_dark="Dark mode", undo="↩ Undo", redo="↪ Redo", active_project="Active project",
        no_project="No project is open. Start with 'New Analysis'.", created_by="Developer: Hamid Yarali",
        projects="Projects", images_done="Images processed", charts_found="Charts detected", series_count="Data series",
        points_count="Extracted points", fits_count="Fitted equations", recent_projects="Recent projects", last_events="Latest analyses",
        open="Open", copy="Copy", delete="Delete", download="Download", upload_files="Chart files (PNG, JPG, TIFF, BMP, WEBP, SVG, PDF)",
        drag_hint="Drag & drop or browse", start_analysis="Start automatic analysis", settings="Extraction settings",
        preview="Preview", try_sample="Try a sample (Sample Data)", sample_note="Sample Data - synthetic chart with ground truth",
        running="Processing…", cancel_hint="To cancel, click any other button (the run stops).", done="Analysis complete",
        failed="Processing error", pdf_page="PDF page", original="Original image", processed="Processed image",
        panel="Panel", plot_area="Plot area", calibration="Axis calibration", axis_info="Axis titles and units",
        apply="Apply", apply_rerun="Apply and re-extract", rotation="Manual rotation (deg)", scale_type="Scale type",
        series="Series", select_series="Select series", rename="Rename", color="Colour", add_point="Add point", delete_points="Delete points",
        apply_edits="Apply edits", redigitize="Re-extract with these settings", n_points="Number of points", sampling="Sampling method",
        search="Search", filter_status="Status filter", columns="Columns", copy_data="Copy data", run_analysis="Run analysis",
        models="Models", compare_models="Compare models", equations="Equations", derivative="Derivative", integral="Integral",
        generate="Generate outputs", language_report="Report language", formats="Output formats", download_all="Download all (ZIP)",
        quality="Extraction quality", warnings="Warnings", ok_saved="Saved", needs_calib="Axis calibration is incomplete: enter tick values.",
        ocr_missing="Tesseract OCR is not installed. Installation help:", approx_note="Fitted models are approximations, not the true law.",
        not_independent="Dense points are not independent: p-values are not statistically meaningful.", import_zip="Restore a project from ZIP",
        export_zip="Export project as ZIP", search_projects="Search projects", no_data="No data available.", chart_type="Chart type",
        override_type="Override chart type manually", sample_data="Sample data", hint_manual="Manual setting", legend_name="Legend name",
        undo_done="Undone", redo_done="Redone", nothing_undo="Nothing to undo",
    ),
}


def lang() -> str:
    return st.session_state.get("lang", "fa")


def t(key: str) -> str:
    return STR.get(lang(), STR["fa"]).get(key) or STR["en"].get(key, key)
