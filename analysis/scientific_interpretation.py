"""Rule-based, data-driven scientific description (Persian / English). Every sentence is generated from numbers
that were actually extracted; nothing is asserted without data support."""
from __future__ import annotations

from models.chart_types import chart_label
from models.data_models import ChartResult


def f(v, n=4) -> str:
    if v is None:
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{v:.{n}g}"


def _unit(ax) -> str:
    return (ax.unit if ax is not None and ax.unit else "")


def _val(v, unit, lang) -> str:
    if unit:
        return f"{f(v)} {unit}"
    return f"{f(v)} ({'واحد نامشخص' if lang == 'fa' else 'unit unknown'})"


_TXT = {
    "fa": dict(
        overview="این تصویر یک «{ctype}» با {n} سری داده است. محور افقی: {xn}؛ محور عمودی: {yn}.",
        no_series="هیچ سری داده‌ای به‌صورت خودکار شناسایی نشد؛ نتیجه‌ای برای تفسیر وجود ندارد.",
        series_head="سری «{name}»:",
        range="مقدار بر روی بازه X از {x0} تا {x1} استخراج شد؛ مقدار ابتدا {ys} و مقدار انتها {ye} است.",
        peak="بیشینه مقدار {ymax} در X = {xmax} رخ می‌دهد؛ کمینه {ymin} در X = {xmin} است.",
        mono_increasing="روند کلی افزایشی (یکنواخت) است.",
        mono_decreasing="روند کلی کاهشی (یکنواخت) است.",
        mono_nondec="روند کلی غیرکاهشی است و بخش‌های تقریباً ثابت (پلاتو) دارد.",
        mono_noninc="روند کلی غیرافزایشی است و بخش‌های تقریباً ثابت (پلاتو) دارد.",
        mono_non="روند یکنواخت نیست؛ نقاط بازگشت (بیشینه/کمینه محلی) در X = {pts} مشاهده می‌شود.",
        slope="بیشینه شیب محاسبه‌شده {s} (واحد Y بر واحد X) در X = {x} است.",
        init_slope="شیب خطی اولیه (پنجره‌ای با R² ≥ ۰٫۹۸) برابر {s} در بازه X = {x0} تا {x1} است.",
        post_peak="پس از قله، مقدار از {pk} تا {last} کاهش یافته ({pct}٪ افت).",
        area="مساحت زیر منحنی (قاعده ذوزنقه) برابر {a} {u} است.",
        fit="بهترین مدل تقریبی با معیار انتخاب ساده‌ترین مدل مناسب: «{m}» با R² = {r2} و RMSE = {rmse}: {eq}",
        infl="نقطه(های) عطف تقریبی در X = {pts} برآورد شد.",
        compare_head="مقایسه سری‌ها:",
        highest="بالاترین مقدار بیشینه مربوط به «{n}» ({v}) است؛ پایین‌ترین بیشینه مربوط به «{n2}» ({v2}).",
        largest_auc="بیشترین مساحت زیر منحنی مربوط به «{n}» ({v}) است.",
        pair="بیشترین اختلاف مطلق بین «{a}» و «{b}» برابر {d} در X = {x} است؛ RMSD = {rmsd}.",
        corr="ضریب همبستگی پیرسون بین «{a}» و «{b}» روی بازه مشترک {r} است (شباهت شکل، نه معناداری آماری).",
        crossings="{k} نقطه تقاطع بین منحنی‌ها یافت شد؛ نخستین: «{a}» و «{b}» در X = {x}.",
        no_cross="تقاطعی بین منحنی‌ها در بازه مشترک یافت نشد.",
        anomalies_head="نقاط غیرعادی و هشدارها:",
        low_conf="اطمینان استخراج سری «{n}» پایین است ({c}).",
        gaps="سری «{n}» فقط در {p}٪ از بازه X قابل مشاهده بود (هم‌پوشانی یا شکاف)؛ بخش‌های گمشده درون‌یابی شده‌اند.",
        outl="{k} نقطه پرت در سری «{n}» علامت‌گذاری شد.",
        units_unknown="عنوان/واحد محور نامشخص است و برای آن واحد حدس زده نشد.",
        no_anom="مورد غیرعادی مشخصی در داده‌های استخراج‌شده شناسایی نشد.",
        lim_head="محدودیت‌های استخراج و تفسیر:",
        cal="کیفیت کلی استخراج: {g} (امتیاز {s}).",
    ),
    "en": dict(
        overview="The image is a '{ctype}' with {n} data series. Horizontal axis: {xn}; vertical axis: {yn}.",
        no_series="No data series could be detected automatically; there is nothing to interpret.",
        series_head="Series '{name}':",
        range="Values were extracted over X = {x0} to {x1}; the first value is {ys} and the last value is {ye}.",
        peak="The maximum value {ymax} occurs at X = {xmax}; the minimum {ymin} occurs at X = {xmin}.",
        mono_increasing="The overall trend is monotonically increasing.",
        mono_decreasing="The overall trend is monotonically decreasing.",
        mono_nondec="The overall trend is non-decreasing with near-constant plateaus.",
        mono_noninc="The overall trend is non-increasing with near-constant plateaus.",
        mono_non="The trend is not monotonic; turning points (local max/min) appear at X = {pts}.",
        slope="The maximum computed slope is {s} (Y-units per X-unit) at X = {x}.",
        init_slope="The steepest linear window (R² ≥ 0.98) has a slope of {s} over X = {x0} to {x1}.",
        post_peak="After the peak the value falls from {pk} to {last} ({pct}% drop).",
        area="The area under the curve (trapezoidal rule) is {a} {u}.",
        fit="Best approximate model (simplest adequate model): '{m}' with R² = {r2}, RMSE = {rmse}: {eq}",
        infl="Approximate inflection point(s) at X = {pts}.",
        compare_head="Series comparison:",
        highest="The highest maximum belongs to '{n}' ({v}); the lowest maximum belongs to '{n2}' ({v2}).",
        largest_auc="The largest area under the curve belongs to '{n}' ({v}).",
        pair="The largest absolute difference between '{a}' and '{b}' is {d} at X = {x}; RMSD = {rmsd}.",
        corr="Pearson correlation between '{a}' and '{b}' over the common range is {r} (shape similarity, not statistical significance).",
        crossings="{k} crossing point(s) between curves were found; first: '{a}' and '{b}' at X = {x}.",
        no_cross="No crossings between curves were found on the common range.",
        anomalies_head="Unusual points and warnings:",
        low_conf="Extraction confidence for series '{n}' is low ({c}).",
        gaps="Series '{n}' was visible over only {p}% of its X-extent (overlap or gaps); missing parts were interpolated.",
        outl="{k} outlying point(s) were flagged in series '{n}'.",
        units_unknown="The axis title/unit is unknown and no unit was guessed.",
        no_anom="No unusual behaviour was identified in the extracted data.",
        lim_head="Extraction and interpretation limitations:",
        cal="Overall extraction quality: {g} (score {s}).",
    ),
}
_GRADE_FA = dict(excellent="عالی", good="خوب", fair="متوسط", poor="ضعیف")
_LIMS = {
    "fa": ["داده‌ها از تصویر رستری/برداری بازسازی شده‌اند؛ نقاط بازسازی‌شده و درون‌یابی‌شده اندازه‌گیری‌های اصلی آزمایش نیستند.",
           "معادلات برازش‌شده فقط مدل‌های تقریبی‌اند و با قانون واقعی پدیده یکسان فرض نمی‌شوند.",
           "مشتق و انتگرال تخمین‌های عددی روی نقاط استخراج‌شده هستند و نویز در مشتق تقویت می‌شود.",
           "نوع نوار خطا/ناحیه سایه (SD، SE یا CI) از روی تصویر قابل تشخیص نیست مگر در توضیح نمودار ذکر شده باشد.",
           "آزمون‌های آماری روی نقاط متراکم (وابسته) معنادار نیستند؛ فقط توصیف شکل منحنی‌اند."],
    "en": ["Data were reconstructed from a raster/vector image; reconstructed and interpolated points are not original measurements.",
           "Fitted equations are approximate models and must not be confused with the true law of the phenomenon.",
           "Derivatives and integrals are numerical estimates from the extracted points; derivatives amplify noise.",
           "The type of error bars / shaded regions (SD, SE or CI) cannot be determined from the image unless stated in the caption.",
           "Statistical tests on dense (dependent) points are not meaningful; they only describe curve shape."],
}


def interpret(chart: ChartResult, lang: str = "fa") -> dict:
    T = _TXT["fa" if lang == "fa" else "en"]
    L = "fa" if lang == "fa" else "en"
    an = chart.analysis or {}
    xa, ya = chart.x_axis, chart.y_axis
    xn = xa.display_name if xa and xa.display_name != "unknown" else ("نامشخص" if L == "fa" else "unknown")
    yn = ya.display_name if ya and ya.display_name != "unknown" else ("نامشخص" if L == "fa" else "unknown")
    paras, highlights = [], []
    if not chart.series:
        return dict(paragraphs=[T["no_series"]], limitations=_LIMS[L], highlights=[])
    paras.append(T["overview"].format(ctype=chart_label(chart.chart_type, L), n=len(chart.series), xn=xn, yn=yn))
    yu, xu = _unit(ya), _unit(xa)
    for s in chart.series:
        a = (an.get("series") or {}).get(s.name) or {}
        if not a or a.get("skipped") or "features" not in a:
            continue
        ft, mt = a["features"], a.get("metrics", {})
        lines = [T["series_head"].format(name=s.name)]
        lines.append(T["range"].format(x0=f(ft["start"]["x"]), x1=f(ft["end"]["x"]), ys=_val(ft["start"]["y"], yu, L), ye=_val(ft["end"]["y"], yu, L)))
        lines.append(T["peak"].format(ymax=_val(ft["global_max"]["y"], yu, L), xmax=f(ft["global_max"]["x"]),
                                      ymin=_val(ft["global_min"]["y"], yu, L), xmin=f(ft["global_min"]["x"])))
        mono = ft.get("monotonicity", "")
        if mono == "increasing":
            lines.append(T["mono_increasing"])
        elif mono == "decreasing":
            lines.append(T["mono_decreasing"])
        elif mono.startswith("non-decreasing"):
            lines.append(T["mono_nondec"])
        elif mono.startswith("non-increasing"):
            lines.append(T["mono_noninc"])
        else:
            pts = ", ".join(f(t["x"]) for t in ft.get("turning_points", [])[:5]) or "—"
            lines.append(T["mono_non"].format(pts=pts))
        d = a.get("derivative")
        if d:
            lines.append(T["slope"].format(s=f(d["max_slope"]["value"]), x=f(d["max_slope"]["x"])))
            if d.get("inflection_points"):
                lines.append(T["infl"].format(pts=", ".join(f(p["x"]) for p in d["inflection_points"][:4])))
        if mt.get("max_slope_linear_window"):
            w = mt["max_slope_linear_window"]
            lines.append(T["init_slope"].format(s=f(w["slope"]), x0=f(w["x0"]), x1=f(w["x1"])))
        if mt.get("drop_after_peak_percent") and mt["drop_after_peak_percent"] > 5 and ft["global_max"]["x"] < ft["end"]["x"]:
            lines.append(T["post_peak"].format(pk=f(mt["peak_value"]), last=f(mt["last_value"]), pct=f(mt["drop_after_peak_percent"], 3)))
        ig = a.get("integral") or {}
        if ig.get("ok"):
            lines.append(T["area"].format(a=f(ig["trapezoid"]), u=(an.get("units", {}).get("area") or ("(واحد نامشخص)" if L == "fa" else "(unit unknown)"))))
        fits = a.get("fits") or {}
        if fits.get("best"):
            b = next((m for m in fits["models"] if m["name"] == fits["best"]), None)
            if b:
                lines.append(T["fit"].format(m=b["name"], r2=f(b["metrics"]["r2"], 5), rmse=f(b["metrics"]["rmse"]), eq=b["equation"]["text"]))
        paras.append(" ".join(lines))
    comp = next(iter((an.get("comparison") or {}).values()), None)
    if comp and len(comp.get("per_series", {})) >= 2:
        lines = [T["compare_head"]]
        mx = comp["ranking"]["max"]
        per = comp["per_series"]
        lines.append(T["highest"].format(n=mx[0], v=_val(per[mx[0]]["max"], yu, L), n2=mx[-1], v2=_val(per[mx[-1]]["max"], yu, L)))
        au = comp["ranking"]["auc"]
        lines.append(T["largest_auc"].format(n=au[0], v=f(per[au[0]]["auc"])))
        pairs = [p for p in comp.get("pairs", []) if p.get("common_range")]
        if pairs:
            p = max(pairs, key=lambda r: r["max_abs_difference"])
            lines.append(T["pair"].format(a=p["a"], b=p["b"], d=_val(p["max_abs_difference"], yu, L), x=f(p["x_at_max_difference"]), rmsd=f(p["rmsd"])))
            pc = [p for p in pairs if "pearson_r" in p]
            if pc:
                p = pc[0]
                lines.append(T["corr"].format(a=p["a"], b=p["b"], r=f(p["pearson_r"], 3)))
        ix = an.get("intersections") or []
        lines.append(T["crossings"].format(k=len(ix), a=ix[0]["series_a"], b=ix[0]["series_b"], x=f(ix[0]["x"])) if ix else T["no_cross"])
        paras.append(" ".join(lines))
    an_lines = [T["anomalies_head"]]
    found = False
    for s in chart.series:
        if s.confidence and s.confidence < 0.55:
            an_lines.append(T["low_conf"].format(n=s.name, c=f(s.confidence, 2)))
            found = True
        cov = s.extra.get("coverage", 1.0)
        if cov is not None and cov < 0.85:
            an_lines.append(T["gaps"].format(n=s.name, p=f(cov * 100, 3)))
            found = True
        o = ((an.get("series") or {}).get(s.name) or {}).get("outliers") or []
        if o:
            an_lines.append(T["outl"].format(k=len(o), n=s.name))
            found = True
    if (xa is None or not xa.title) or (ya is None or not ya.title):
        an_lines.append(T["units_unknown"])
        found = True
    if not found:
        an_lines.append(T["no_anom"])
    paras.append(" ".join(an_lines))
    q = chart.quality or {}
    if q:
        g = q.get("grade", "")
        paras.append(T["cal"].format(g=_GRADE_FA.get(g, g) if L == "fa" else g, s=f(q.get("overall"), 3)))
    return dict(paragraphs=paras, limitations=_LIMS[L], highlights=highlights)
