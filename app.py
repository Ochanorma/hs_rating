import os

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="高校野球レーティング", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
@media (max-width: 640px) {
  .block-container { padding: 1rem 0.6rem 3rem 0.6rem; }
  h1 { font-size: 1.4rem !important; }
  h2, h3 { font-size: 1.1rem !important; }
  [data-testid="stMetricValue"] { font-size: 1.1rem; }
  [data-testid="stMetricLabel"] { font-size: 0.75rem; }
  button[data-baseweb="tab"] { padding: 0.4rem 0.5rem; font-size: 0.8rem; }
}
</style>
""", unsafe_allow_html=True)

NAT = {"選抜", "夏の甲子園", "神宮大会", "甲子園交流試合"}


def hl(row):
    """全国大会の行を太字+黄色にする"""
    if row.get("大会種別") in NAT:
        return ["font-weight: bold; background-color: #fff3b0; color: #000"] * len(row)
    return [""] * len(row)


@st.cache_data(ttl=600)
def load():
    df = pd.read_csv("output/ratings.csv")
    mcols = sorted([c for c in df.columns if c.startswith("M_")])
    df["label"] = df["team"].astype(str) + "(" + df["pref"].astype(str) + ")"
    df["rank_now"] = df["rating"].rank(ascending=False, method="min")
    df["prank_now"] = df.groupby("pref")["rating"].rank(
        ascending=False, method="min")
    for c in mcols:
        df["rank_" + c] = df[c].rank(ascending=False, method="min")
        df["prank_" + c] = df.groupby("pref")[c].rank(
            ascending=False, method="min")
    if "閉校月" in df.columns:
        df["閉校月"] = df["閉校月"].fillna("")
    return df, mcols


@st.cache_data(ttl=600)
def load_csv(path):
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


df, mcols = load()
stt = load_csv("output/school_tournament.csv")
tgm = load_csv("output/tournament_games.csv")
tms = load_csv("output/tournament_master.csv")
mlabels = [c[2:] for c in mcols]
tlabels = ["最新"] + mlabels


def colof(t):
    return "rating" if t == "最新" else "M_" + t


def expand(rows, keys):
    """行内のリストを、1校1セルの列に展開する。keys={リスト名: 列の接頭辞}"""
    mx = {}
    for k in keys:
        mx[k] = max([len(r[k]) for r in rows] + [0])
    out = []
    for r in rows:
        nr = {k: v for k, v in r.items() if k not in keys}
        for k, pre in keys.items():
            for i in range(mx[k]):
                nr[pre + str(i + 1)] = r[k][i] if i < len(r[k]) else ""
        out.append(nr)
    return pd.DataFrame(out)


# ---------- サイドバー ----------
st.sidebar.header("絞り込み(ランキング・推移)")
regions = sorted(df["region"].dropna().unique())
sel_reg = st.sidebar.multiselect("地区", regions, default=regions)
prefs = sorted(df[df["region"].isin(sel_reg)]["pref"].dropna().unique())
sel_pref = st.sidebar.multiselect("都道府県(空欄=すべて)", prefs)
min_games = st.sidebar.slider("最低試合数", 0, int(df["games"].max()), 5)
rd_max = int(df["rd_out"].max()) + 1
max_rd = st.sidebar.slider("RD上限", 0, rd_max, rd_max)
kw = st.sidebar.text_input("学校名で検索")

f = df[df["region"].isin(sel_reg)]
if "閉校月" in f.columns and mlabels:
    _last = max(mlabels)
    f = f[(f["閉校月"] == "") | (f["閉校月"] > _last)]
if sel_pref:
    f = f[f["pref"].isin(sel_pref)]
f = f[(f["games"] >= min_games) & (f["rd_out"] <= max_rd)]
if kw:
    f = f[f["team"].str.contains(kw, na=False)]

st.title("高校野球レーティング")
st.caption(f"絞り込み後 {len(f)} 校 / 全 {len(df)} 校。"
           "月初の値は月ごとに全校平均を1500に揃えています。"
           "ランキングの月初時点は当時の校名で表示します。")

tabs = st.tabs(["ランキング", "推移比較", "学校詳細", "都道府県詳細", "大会結果"])

# ---------- 1. ランキング ----------
with tabs[0]:
    if sel_pref:
        scope = "県内順位"
    elif len(sel_reg) < len(regions):
        scope = "地区順位"
    else:
        scope = "全国順位"
    st.caption("順位の基準:" + scope + "(サイドバーの絞り込みに連動)")

    c1, c2, c3 = st.columns(3)
    t_sel = c1.selectbox("時点", tlabels, index=0, key="rk_time")
    t_cmp = c2.selectbox("比較時点(順位の増減)", ["なし"] + tlabels, key="rk_cmp")
    n_show = c3.slider("表示件数", 10, 300, 50, key="rk_n")
    compact = st.checkbox("スマホ向け(列を絞る)", value=False, key="rk_compact")

    def rank_in(frame, tl):
        """絞り込み後の学校だけで順位を付け、その時点の校名を付ける"""
        c = colof(tl)
        x = frame[frame[c].notna()].copy()
        x["順位"] = x[c].rank(ascending=False, method="min").astype(int)
        x["レーティング"] = x[c].round(1)
        nc = "N_" + tl
        if tl != "最新" and nc in x.columns:
            x["校名"] = x[nc].fillna(x["team"])
        else:
            x["校名"] = x["team"]
        return x.sort_values("順位")

    t = rank_in(f, t_sel)
    t = t.rename(columns={"順位": scope})
    show = [scope, "校名", "pref", "region", "レーティング"]
    if t_sel == "最新":
        show += ["rd_out", "games", "W", "L"]
    if t_cmp != "なし":
        tc = rank_in(f, t_cmp).set_index("school_id")["順位"]
        t["比較時点の順位"] = t["school_id"].map(tc)
        t["順位増減(+は上昇)"] = t["比較時点の順位"] - t[scope]
        show += ["比較時点の順位", "順位増減(+は上昇)"]
    st.download_button("この表をCSV保存",
                       t[show].to_csv(index=False).encode("utf-8-sig"),
                       "ranking_" + t_sel + ".csv", "text/csv")
    if compact:
        show = [scope, "校名", "pref", "レーティング"]
    st.dataframe(t[show].head(n_show), hide_index=True,
                 use_container_width=True)

    st.subheader("時点別ランキング比較(横:日付、縦:順位)")
    d1, d2 = st.columns(2)
    default_t = tlabels[-4:] if len(tlabels) > 4 else tlabels
    pick_t = d1.multiselect("表示する時点", tlabels, default=default_t,
                            key="rk_cols")
    top_n = d2.slider("上位N位", 5, 100, 20, key="rk_topn")
    if not pick_t:
        st.info("時点を選んでください。")
    else:
        cols_t = {}
        for tl in pick_t:
            x = rank_in(f, tl)
            x = x[x["順位"] <= top_n]
            cell = {}
            for _, rw in x.iterrows():
                txt = f"{rw['校名']} ({rw['レーティング']:.1f})"
                if rw["順位"] in cell:
                    cell[rw["順位"]] += " / " + txt
                else:
                    cell[rw["順位"]] = txt
            cols_t[tl] = pd.Series(cell)
        cmp_df = pd.DataFrame(cols_t).reindex(range(1, top_n + 1)).fillna("")
        cmp_df.index.name = scope
        st.dataframe(cmp_df, use_container_width=True)
        st.download_button("比較表をCSV保存",
                           cmp_df.to_csv().encode("utf-8-sig"),
                           "ranking_compare.csv", "text/csv")

# ---------- 2. 推移比較 ----------
with tabs[1]:
    if len(mlabels) < 2:
        st.warning("ratings.csv に M_ 列が足りません。")
    else:
        c1, c2 = st.columns(2)
        metric = c1.radio("指標", ["レーティング", "全国順位", "県内順位"],
                          horizontal=True, key="tr_metric")
        mode = c2.radio("学校の選び方", ["手動で選ぶ", "指定時点の上位N校"],
                        horizontal=True, key="tr_mode")
        period = st.select_slider("期間", options=mlabels,
                                  value=(mlabels[0], mlabels[-1]), key="tr_period")
        months = mlabels[mlabels.index(period[0]):mlabels.index(period[1]) + 1]
        if mode == "手動で選ぶ":
            cand = f.sort_values("rating", ascending=False)["label"].tolist()
            picks = st.multiselect("学校を選択", cand, default=cand[:5], key="tr_picks")
        else:
            d1, d2 = st.columns(2)
            t_top = d1.selectbox("基準時点", tlabels, index=len(tlabels) - 1,
                                 key="tr_top_t")
            n_top = d2.slider("上位N校", 3, 30, 10, key="tr_top_n")
            base = f[f[colof(t_top)].notna()].sort_values(colof(t_top), ascending=False)
            picks = base["label"].head(n_top).tolist()
        sub = df[df["label"].isin(picks)]
        rows = []
        for _, r in sub.iterrows():
            for m in months:
                rows.append(dict(label=r["label"], month=m,
                                 レーティング=r["M_" + m],
                                 全国順位=r["rank_M_" + m],
                                 県内順位=r["prank_M_" + m]))
        long = pd.DataFrame(rows)
        if long.empty:
            st.info("学校を選んでください。")
        else:
            long = long.dropna(subset=[metric])
            fig = px.line(long, x="month", y=metric, color="label",
                          markers=True, title=metric + "の推移")
            if metric != "レーティング":
                fig.update_yaxes(autorange="reversed")
            fig.update_layout(xaxis_title="", height=420,
                              legend=dict(orientation="h", y=-0.3))
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(long.pivot(index="label", columns="month",
                                    values=metric).round(1),
                         use_container_width=True)

# ---------- 3. 学校詳細 ----------
with tabs[2]:
    names = df.sort_values("rating", ascending=False)["label"].tolist()
    one = st.selectbox("学校を選択", names, key="dt_school")
    r = df[df["label"] == one].iloc[0]
    sid = int(r["school_id"])
    m1, m2, m3 = st.columns(3)
    m4, m5 = st.columns(2)
    m1.metric("レーティング", f"{r['rating']:.1f}")
    m2.metric("全国順位", f"{int(r['rank_now'])} / {len(df)}")
    npref = int((df["pref"] == r["pref"]).sum())
    m3.metric("県内順位", f"{int(r['prank_now'])} / {npref}")
    m4.metric("勝-敗", f"{int(r['W'])}-{int(r['L'])}")
    m5.metric("RD(不確かさ)", f"{r['rd_out']:.1f}")

    # 統合前の旧ID(元ID)と当時の校名の一覧
    ids = []
    if stt is not None:
        ss_ = stt[stt["現ID"] == sid].sort_values("最終戦日")
        if not ss_.empty:
            g_ = ss_.groupby("ID").agg(first=("初戦日", "min"),
                                       name=("校名", "last"))
            g_ = g_.sort_values("first")
            ids = [(int(i), n) for i, n in zip(g_.index, g_["name"])]
    merged = len(ids) > 1
    if merged:
        st.info("統合校です。統合前の学校ごとに表を分けて表示します:"
                + " → ".join(n + "(ID " + str(i) + ")" for i, n in ids))

    sub_t = st.tabs(["レーティング推移", "学校ページ(大会別成績)", "学校→試合"])

    with sub_t[0]:
        hist = pd.DataFrame({
            "時点": mlabels,
            "当時の校名": [r.get("N_" + m) for m in mlabels],
            "レーティング": [r["M_" + m] for m in mlabels],
            "全国順位": [r["rank_M_" + m] for m in mlabels],
            "県内順位": [r["prank_M_" + m] for m in mlabels]})
        hist = hist.dropna(subset=["レーティング"])
        if hist.empty:
            st.info("月初の記録がありません。")
        else:
            fig1 = px.line(hist, x="時点", y="レーティング", markers=True,
                           title="レーティング推移")
            fig2 = px.line(hist, x="時点", y="全国順位", markers=True,
                           title="全国順位の推移")
            fig2.update_yaxes(autorange="reversed")
            fig3 = px.line(hist, x="時点", y="県内順位", markers=True,
                           title="県内順位の推移")
            fig3.update_yaxes(autorange="reversed")
            for fg in (fig1, fig2, fig3):
                fg.update_layout(height=320)
            st.plotly_chart(fig1, use_container_width=True)
            st.plotly_chart(fig2, use_container_width=True)
            st.plotly_chart(fig3, use_container_width=True)
            hn = [x for x in hist["当時の校名"].dropna().unique()]
            if len(hn) > 1:
                st.caption("レーティングは統合後も1本の値として更新されています。"
                           "表は当時の校名ごとに区切っています。")
                for nm in hn:
                    st.markdown("**" + str(nm) + "** の時期")
                    st.dataframe(hist[hist["当時の校名"] == nm].round(1),
                                 hide_index=True, use_container_width=True)
            else:
                st.dataframe(hist.round(1), hide_index=True,
                             use_container_width=True)

    with sub_t[1]:
        if stt is None:
            st.warning("output/school_tournament.csv がありません。")
        else:
            s = stt[stt["現ID"] == sid].copy()
            if s.empty:
                st.info("この学校の大会成績はありません。")
            else:
                kinds = sorted(s["大会種別"].unique())
                pick_k = st.multiselect("大会種別", kinds, default=kinds,
                                        key="sc_kinds")
                s = s[s["大会種別"].isin(pick_k)].sort_values(
                    ["年", "初戦日"], ascending=[False, False])
                cols = ["年", "大会種別", "大会名", "校名", "結果", "最終ラウンド",
                        "試合数", "勝", "敗", "総得点", "総失点", "初戦日", "最終戦日"]
                st.caption("黄色の太字の行は全国大会(選抜・夏の甲子園・神宮大会など)です。校名は当時のものです。")
                groups = ids if merged else [(None, None)]
                for gid, gname in groups:
                    part = s if gid is None else s[s["ID"] == gid]
                    if merged:
                        st.markdown("### " + str(gname) + "(ID " + str(gid) + ")")
                    a, b, c = st.columns(3)
                    a.metric("出場大会数", len(part))
                    b.metric("優勝", int((part["結果"] == "優勝").sum()))
                    c.metric("準優勝", int((part["結果"] == "準優勝").sum()))
                    if part.empty:
                        st.info("該当なし")
                    else:
                        st.dataframe(
                            part[cols].reset_index(drop=True).style.apply(hl, axis=1),
                            hide_index=True, use_container_width=True)
                if merged:
                    st.markdown("### 合計(統合後)")
                    a, b, c = st.columns(3)
                    a.metric("出場大会数", len(s))
                    b.metric("優勝", int((s["結果"] == "優勝").sum()))
                    c.metric("準優勝", int((s["結果"] == "準優勝").sum()))

    with sub_t[2]:
        if tgm is None:
            st.warning("output/tournament_games.csv がありません。")
        else:
            gm_all = tgm[(tgm["校1現ID"] == sid) | (tgm["校2現ID"] == sid)].copy()
            if gm_all.empty:
                st.info("この学校の試合はありません。")
            else:
                gy = sorted(gm_all["年"].unique(), reverse=True)
                sel_y = st.multiselect("年", gy, default=gy, key="gm_years")

                def game_table(base, oid):
                    gm = base.copy()
                    if oid is not None:
                        gm = gm[(gm["校1ID"] == oid) | (gm["校2ID"] == oid)]
                        first = gm["校1ID"] == oid
                    else:
                        first = gm["校1現ID"] == sid
                    gm["自校"] = gm["校1"].where(first, gm["校2"])
                    gm["相手"] = gm["校2"].where(first, gm["校1"])
                    gm["相手県"] = gm["校2県"].where(first, gm["校1県"])
                    gm["自得点"] = gm["得点1"].where(first, gm["得点2"])
                    gm["相手得点"] = gm["得点2"].where(first, gm["得点1"])
                    gm["結果"] = (gm["自得点"] > gm["相手得点"]).map(
                        {True: "○", False: "●"})
                    gm["スコア"] = (gm["自得点"].astype(str) + "-"
                                 + gm["相手得点"].astype(str))
                    gm = gm[gm["年"].isin(sel_y)].sort_values(
                        ["日付", "ラウンド順"], ascending=[False, False])
                    return gm

                groups = ids if merged else [(None, None)]
                for gid, gname in groups:
                    gm = game_table(gm_all, gid)
                    if merged:
                        st.markdown("### " + str(gname) + "(ID " + str(gid) + ")")
                    st.caption(f"{len(gm)}試合 / {int((gm['結果'] == '○').sum())}勝"
                               f"{int((gm['結果'] == '●').sum())}敗(校名は当時のもの)")
                    st.dataframe(gm[["日付", "大会名", "ラウンド", "自校", "結果",
                                     "スコア", "相手", "相手県"]],
                                 hide_index=True, use_container_width=True)

# ---------- 4. 都道府県詳細 ----------
with tabs[3]:
    if stt is None:
        st.warning("output/school_tournament.csv がありません。")
    else:
        plist = sorted(set(df["pref"].dropna().unique())
                       | set(stt["都道府県"].dropna().unique()))
        pf = st.selectbox("都道府県", plist,
                          index=plist.index("神奈川") if "神奈川" in plist else 0,
                          key="pf_sel")
        order_new = st.radio("並び順", ["古い順", "新しい順"], horizontal=True,
                             key="pf_order") == "新しい順"
        sp = stt[stt["都道府県"] == pf].copy()

        dp = df[df["pref"] == pf]
        a, b, c = st.columns(3)
        a.metric("登録校数", len(dp))
        b.metric("平均レーティング", f"{dp['rating'].mean():.1f}" if len(dp) else "-")
        c.metric("上位10校平均",
                 f"{dp['rating'].nlargest(10).mean():.1f}" if len(dp) else "-")

        st.subheader("県大会の結果(優勝・準優勝・ベスト4・ベスト8)")
        pk = ["春季県大会", "夏の地方大会", "夏(独自大会)", "秋季県大会"]
        sk = sp[sp["大会種別"].isin(pk)]
        ysel = sorted(sk["年"].unique(), reverse=True)
        ypick = st.multiselect("年", ysel, default=ysel, key="pf_years")
        kpick = st.multiselect("大会種別", pk, default=pk, key="pf_kinds")
        sk = sk[sk["年"].isin(ypick) & sk["大会種別"].isin(kpick)]
        if sk.empty:
            st.info("該当なし")
        else:
            rows = []
            for (y, k, tid, nm), d in sk.groupby(["年", "大会種別", "大会ID", "大会名"]):
                def lst(res):
                    return d[d["結果"] == res]["校名"].tolist()
                w1 = lst("優勝")
                w2 = lst("準優勝")
                note = ""
                if len(w1) == 0:
                    note = "優勝校なし(打ち切り・未実施・データなし)"
                elif len(w1) > 1:
                    note = "複数校優勝"
                rows.append(dict(
                    最終戦日=str(d["最終戦日"].max()), 年=y, 大会種別=k, 大会名=nm,
                    優勝="、".join(w1), 準優勝="、".join(w2), 備考=note,
                    b4=lst("ベスト4"), b8=lst("ベスト8")))
            for r_ in rows:
                if len(r_["b4"]) >= 3:
                    r_["b4"] = ["、".join(r_["b4"])]
                if len(r_["b8"]) >= 5:
                    r_["b8"] = ["、".join(r_["b8"])]
            tb = expand(rows, {"b4": "ベスト4-", "b8": "ベスト8-"})
            tb = tb.sort_values("最終戦日", ascending=not order_new)
            cols_ = [c for c in tb.columns if c != "備考"] + ["備考"]
            tb = tb[cols_]
            st.dataframe(tb, hide_index=True)

        st.subheader("都道府県代表の地区大会・全国大会の成績")
        hk = ["春季地区大会", "秋季地区大会", "選抜", "夏の甲子園",
              "神宮大会", "甲子園交流試合"]
        hp = sp[sp["大会種別"].isin(hk)]
        if hp.empty:
            st.info("該当なし")
        else:
            kp2 = [k for k in hk if k in set(hp["大会種別"])]
            kk = st.multiselect("大会種別 ", kp2, default=kp2, key="pf_kinds2")
            hp = hp[hp["大会種別"].isin(kk)].sort_values(
                ["最終戦日", "大会ID"], ascending=not order_new).copy()
            is_ex = hp["大会種別"] == "甲子園交流試合"
            hp.loc[is_ex, "結果"] = hp.loc[is_ex, "結果"].astype(str).map(
                lambda v: "勝利" if "勝ち" in v else "敗戦")
            st.caption("黄色の太字の行は全国大会です。")
            cols2 = ["最終戦日", "年", "大会種別", "大会名", "校名", "結果",
                     "最終ラウンド", "試合数", "勝", "敗"]
            st.dataframe(hp[cols2].reset_index(drop=True).style.apply(hl, axis=1),
                         hide_index=True, use_container_width=True)

# ---------- 5. 大会結果 ----------
with tabs[4]:
    if stt is None or tms is None:
        st.warning("school_tournament.csv / tournament_master.csv がありません。")
    else:
        kinds_all = ["夏の甲子園", "選抜", "神宮大会", "甲子園交流試合",
                     "春季地区大会", "秋季地区大会"]
        kinds_all = [k for k in kinds_all if k in set(stt["大会種別"])]
        kind = st.selectbox("大会種別", kinds_all, key="tn_kind")
        is_reg = kind in ("春季地区大会", "秋季地区大会")
        sub = stt[stt["大会種別"] == kind].copy()

        if kind == "甲子園交流試合":
            if tgm is None:
                st.warning("tournament_games.csv がありません。")
            else:
                gg = tgm[tgm["大会種別"] == "甲子園交流試合"].sort_values(
                    ["年", "日付", "ラウンド順"])
                gg = gg.assign(
                    スコア=gg["得点1"].astype(str) + "-" + gg["得点2"].astype(str),
                    校1表示=gg["校1"] + "(" + gg["校1県"].astype(str) + ")",
                    校2表示=gg["校2"] + "(" + gg["校2県"].astype(str) + ")")
                ys = sorted(gg["年"].unique(), reverse=True)
                ysel2 = st.multiselect("年", ys, default=ys, key="tn_years_ex")
                gg = gg[gg["年"].isin(ysel2)]
                st.caption("優勝・準優勝のない交流試合です。全試合の結果を表示します。")
                st.dataframe(gg[["年", "日付", "校1表示", "スコア", "校2表示", "勝者"]]
                             .rename(columns={"校1表示": "校1", "校2表示": "校2"}),
                             hide_index=True, use_container_width=True)
        else:
            c1, c2 = st.columns(2)
            ys = sorted(sub["年"].unique(), reverse=True)
            ysel2 = c1.multiselect("年", ys, default=ys, key="tn_years")
            sub = sub[sub["年"].isin(ysel2)]

            if is_reg:
                rmap = sub.groupby(["年", "大会ID"])["地区"].agg(
                    lambda s: s.mode().iloc[0] if len(s.mode()) else "")
                sub["大会地区"] = [rmap.get((a, b), "")
                               for a, b in zip(sub["年"], sub["大会ID"])]
                rl = ["すべて"] + sorted([x for x in sub["大会地区"].unique() if x])
                rr = c2.selectbox("地区", rl, key="tn_region")
                if rr != "すべて":
                    sub = sub[sub["大会地区"] == rr]

            rows = []
            for (y, tid, nm), d in sub.groupby(["年", "大会ID", "大会名"]):
                def lab(x):
                    return str(x["校名"]) + "(" + str(x["都道府県"]) + ")"

                def lst(res):
                    return [lab(x) for _, x in d[d["結果"] == res].iterrows()]
                w1 = lst("優勝")
                w2 = lst("準優勝")
                row = dict(年度=y, 大会名=nm)
                if is_reg:
                    row["地区"] = str(d["大会地区"].iloc[0])
                row.update(優勝="、".join(w1), 準優勝="、".join(w2),
                           b4=lst("ベスト4"), b8=lst("ベスト8"))
                row["_id"] = tid
                rows.append(row)

            if not rows:
                st.info("該当なし")
            else:
                tb = expand(rows, {"b4": "ベスト4-", "b8": "ベスト8-"}).sort_values(
                    ["年度", "_id"], ascending=[False, True])
                tb = tb.drop(columns="_id")
                st.dataframe(tb, hide_index=True)
                st.download_button("この表をCSV保存",
                                   tb.to_csv(index=False).encode("utf-8-sig"),
                                   "tournament_" + kind + ".csv", "text/csv")

                if tgm is not None:
                    with st.expander("個別の大会の試合結果を見る"):
                        cand = sub[["年", "大会ID", "大会名"]].drop_duplicates()
                        cand = cand.sort_values(["年", "大会ID"], ascending=[False, True])
                        opts = [str(a) + " " + b + " (" + str(c) + ")"
                                for a, b, c in zip(cand["年"], cand["大会名"], cand["大会ID"])]
                        if opts:
                            pick = st.selectbox("大会", opts, key="tn_one")
                            i = opts.index(pick)
                            yy, ti = int(cand.iloc[i]["年"]), int(cand.iloc[i]["大会ID"])
                            gg = tgm[(tgm["年"] == yy) & (tgm["大会ID"] == ti)].sort_values(
                                ["日付", "ラウンド順"])
                            gg = gg.assign(スコア=gg["得点1"].astype(str) + "-"
                                           + gg["得点2"].astype(str))
                            rds = ["すべて"] + list(dict.fromkeys(gg["ラウンド"]))
                            rsel = st.selectbox("ラウンド", rds, key="tn_round")
                            if rsel != "すべて":
                                gg = gg[gg["ラウンド"] == rsel]
                            st.dataframe(gg[["日付", "ラウンド", "校1", "スコア", "校2", "勝者"]],
                                         hide_index=True, use_container_width=True)
