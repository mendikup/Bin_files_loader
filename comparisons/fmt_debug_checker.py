import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================
# 📊 Results (can be manually updated or read from file)
# ============================================================
results = {
    "mp_no_list": {"time": 33.54, "msgs": 7_596_916},
    "mp_with_list": {"time": 72.58, "msgs": 7_596_916},
    "tp_no_list": {"time": 115.85, "msgs": 7_596_916},
    "tp_with_list": {"time": 180.20, "msgs": 7_596_916},
    "mav_no_list": {"time": 237.64, "msgs": 7_597_096},
    "mav_with_list": {"time": 248.68, "msgs": 7_597_096},
}
baseline_time = results["mav_with_list"]["time"]

# ============================================================
# 🧮 Data Processing
# ============================================================
rows = []
for k, v in results.items():
    rows.append({
        "Method": k,
        "Time (s)": v["time"],
        "Messages": v["msgs"],
        "Faster vs pymavlink (%)": round((baseline_time - v["time"]) / baseline_time * 100, 2)
    })

df = pd.DataFrame(rows)
df = df.sort_values("Time (s)")

# ============================================================
# 🎨 Styling & Custom CSS
# ============================================================
st.set_page_config(page_title="MAVLink Decoder Benchmark", layout="wide")

st.markdown("""
<style>
body {
    background-color: #0e1117;
    color: #f0f2f6;
}
h1, h2, h3 {
    color: #00bcd4;
    font-weight: 700;
}
.big-text {
    font-size: 22px;
    color: #e8eaf6;
    line-height: 1.6;
}
.metric {
    font-size: 20px;
    font-weight: 600;
    color: #8bc34a;
}
.divider {
    border-top: 1px solid #333;
    margin: 25px 0;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# 🧭 Main Header
# ============================================================
st.markdown("<h1 style='text-align:center;'>🚀 MAVLink Decoder Performance Dashboard</h1>", unsafe_allow_html=True)
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

st.markdown("""
<div class='big-text'>
מערכת זו מציגה השוואת ביצועים בין שיטות שונות לפענוח קובצי <b>ArduPilot BIN</b> הכוללים מעל 7.5 מיליון הודעות.
ההשוואה כוללת את:
<ul>
<li><b>Multiprocessing</b> – עיבוד אמיתי במקביל על ליבות שונות.</li>
<li><b>ThreadPool</b> – ריבוי־Threads בתוך תהליך אחד (GIL עדיין קיים).</li>
<li><b>pymavlink</b> – ספריית ה־Reference של ArduPilot לקריאת לוגים.</li>
</ul>
</div>
""", unsafe_allow_html=True)

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

st.markdown("""
<div class='big-text'>
<b>🟢 with_list</b> – כולל שמירה מלאה של כל ההודעות כ־dict בזיכרון.<br>
<b>⚪ no_list</b> – ספירה בלבד, ללא שמירה.
</div>
""", unsafe_allow_html=True)

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# ============================================================
# 📋 Results Table
# ============================================================
st.subheader("📋 Full Results Table")
st.dataframe(df, use_container_width=True, hide_index=True)

# ============================================================
# 📈 Runtime Graph
# ============================================================
st.markdown("<h2 style='text-align:center;'>⏱️ Runtime Comparison (seconds)</h2>", unsafe_allow_html=True)
fig, ax = plt.subplots(figsize=(10, 5))
bars = ax.barh(df["Method"], df["Time (s)"], color=["#66bb6a" if "mp" in x else "#42a5f5" if "tp" in x else "#ef5350" for x in df["Method"]])
ax.set_xlabel("Time (seconds)", fontsize=12)
ax.set_ylabel("Method", fontsize=12)
ax.invert_yaxis()
ax.bar_label(bars, fmt="%.2f s", label_type="edge", fontsize=10)
st.pyplot(fig)

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# ============================================================
# ⚡ Improvement Percentages
# ============================================================
st.markdown("<h2 style='text-align:center;'>⚡ Improvement vs pymavlink (with_list)</h2>", unsafe_allow_html=True)
df_compare = df[df["Method"] != "mav_with_list"].copy()
fig2, ax2 = plt.subplots(figsize=(10, 4))
bars2 = ax2.barh(df_compare["Method"], df_compare["Faster vs pymavlink (%)"], color="#8bc34a")
ax2.set_xlabel("Improvement (%)", fontsize=12)
ax2.axvline(0, color="gray", linewidth=0.8)
ax2.bar_label(bars2, fmt="%.1f%%", label_type="edge", fontsize=10)
ax2.invert_yaxis()
st.pyplot(fig2)

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# ============================================================
# 🧾 Summary
# ============================================================
mp_fast = df.loc[df["Method"] == "mp_no_list", "Time (s)"].values[0]
gain = round((baseline_time - mp_fast) / baseline_time * 100, 1)

st.markdown(f"""
<div class='big-text'>
<h3>📊 סיכום כללי</h3>
<ul>
<li><b>Multiprocessing</b> ללא רשימה הוא המהיר ביותר – <span class='metric'>{mp_fast:.2f} שניות</span>.</li>
<li><b>pymavlink</b> לוקח <span class='metric'>{baseline_time:.2f} שניות</span> באותה משימה.</li>
<li>כלומר, שיפור של כ־<span class='metric'>{gain}%</span> בזמן העיבוד הכולל.</li>
<li><b>ThreadPool</b> מציג ביצועים טובים יחסית, אך איטי בכ־2–3× ממולטי־פרוססינג.</li>
</ul>
</div>
""", unsafe_allow_html=True)

st.success("💡 Tip: You can update the data at the top of the file or load results automatically from a JSON file.")
