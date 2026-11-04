import os

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="高校野球レーティング", layout="wide",
                   initial_sidebar_state="collapsed")

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


def rankof(t):
    return "rank_now" if t == "最新" else "rank_M_" + t


def prankof(t):
    return "prank_now" if t == "最新" else "prank_M_" + t


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
if sel_pref:
    f = f[f["pref"].isin(sel_pref)]
f = f[(f["games"] >= min_games) & (f["rd_out"] <= max_rd)]
if kw:
    f = f[f["team"].str.contains(kw, na=False)]

st.title("高校野球レーティング")
st.caption(f"絞り込み後 {len(f)} 校 / 全 {len(df)} 校。"
           "月初の値は月ごとに全校平均を1500に揃えています。")

tabs = st.tabs(["ランキング", "推移比較", "学校詳細", "都道府県詳細", "大会結果"])

# ---------- 1. ランキング ----------
with tabs[0]:
    c1, c2, c3 = st.columns(3)
    t_sel = c1.selectbox("時点", tlabels, index=0, key="rk_time")
    t_cmp = c2.selectbox("比較時点(順位の増減)", ["なし"] + tlabels, key="rk_cmp")
    n_show = c3.slider("表示件数", 10, 300, 50, key="rk_n")
    col, rcol, pcol = colof(t_sel), rankof(t_sel), prankof(t_sel)
    t = f[f[col].notna()].copy()
    t = t.sort_values(col, ascending=False).reset_index(drop=True)
    t.insert(0, "絞込順位", t.index + 1)
    t["全国順位"] = t[rcol].astype(int)
    t["県内順位"] = t[pcol].astype(int)
    t["レーティング"] = t[col].round(1)
    show = ["絞込順位", "全国順位", "県内順位", "team", "pref", "region",
            "レーティング"]
    if t_cmp != "なし":
        t["比較時点の全国順位"] = t[rankof(t_cmp)]
        t["順位増減(+は上昇)"] = t["比較時点の全国順位"] - t["全国順位"]
        t["比較時点の県内順位"] = t[prankof(t_cmp)]
        t["県内順位増減(+は上昇)"] = t["比較時点の県内順位"] - t["県内順位"]
        show += ["比較時点の全国順位", "順位増減(+は上昇)",
                 "比較時点の県内順位", "県内順位増減(+は上昇)"]
    if t_sel == "最新":
        show += ["rd_out", "games", "W", "L"]
    st.dataframe(t[show].head(n_show), hide_index=True)
    st.download_button("この表をCSV保存",
                       t[show].to_csv(index=False).encode("utf-8-sig"),
                       "ranking_" + t_sel + ".csv", "text/csv")

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
            fig.update_layout(xaxis_title="", height=600,
                              legend=dict(orientation="h", y=-0.25))
            st.plotly_chart(fig)
            st.dataframe(long.pivot(index="label", columns="month",
                                    values=metric).round(1))

# ---------- 3. 学校詳細 ----------
with tabs[2]:
    names = df.sort_values("rating", ascending=False)["label"].tolist()
    one = st.selectbox("学校を選択", names, key="dt_school")
    r = df[df["label"] == one].iloc[0]
    sid = int(r["school_id"])
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("レーティング", f"{r['rating']:.1f}")
    m2.metric("全国順位", f"{int(r['rank_now'])} / {len(df)}")
    npref = int((df["pref"] == r["pref"]).sum())
    m3.metric("県内順位", f"{int(r['prank_now'])} / {npref}")
    m4.metric("勝-敗", f"{int(r['W'])}-{int(r['L'])}")
    m5.metric("RD(不確かさ)", f"{r['rd_out']:.1f}")

    sub_t = st.tabs(["レーティング推移", "学校ページ(大会別成績)", "学校→試合"])

    with sub_t[0]:
        hist = pd.DataFrame({
            "時点": mlabels,
            "レーティング": [r["M_" + m] for m in mlabels],
            "全国順位": [r["rank_M_" + m] for m in mlabels],
            "県内順位": [r["prank_M_" + m] for m in mlabels]})
        hist = hist.dropna(subset=["レーティング"])
        if hist.empty:
            st.info("月初の記録がありません。")
        else:
            g1, g2, g3 = st.columns(3)
            fig1 = px.line(hist, x="時点", y="レーティング", markers=True,
                           title="レーティング推移")
            fig2 = px.line(hist, x="時点", y="全国順位", markers=True,
                           title="全国順位の推移")
            fig2.update_yaxes(autorange="reversed")
            fig3 = px.line(hist, x="時点", y="県内順位", markers=True,
                           title="県内順位の推移")
            fig3.update_yaxes(autorange="reversed")
            g1.plotly_chart(fig1)
            g2.plotly_chart(fig2)
            g3.plotly_chart(fig3)
            st.dataframe(hist.round(1), hide_index=True)

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
                a, b, c = st.columns(3)
                a.metric("出場大会数", len(s))
                b.metric("優勝", int((s["結果"] == "優勝").sum()))
                c.metric("準優勝", int((s["結果"] == "準優勝").sum()))
                cols = ["年", "大会種別", "大会名", "結果", "最終ラウンド",
                        "試合数", "勝", "敗", "総得点", "総失点", "初戦日", "最終戦日"]
                st.caption("黄色の太字の行は全国大会(選抜・夏の甲子園・神宮大会など)です。")
                st.dataframe(s[cols].reset_index(drop=True).style.apply(hl, axis=1),
                             hide_index=True)

    with sub_t[2]:
        if tgm is None:
            st.warning("output/tournament_games.csv がありません。")
        else:
            gm = tgm[(tgm["校1現ID"] == sid) | (tgm["校2現ID"] == sid)].copy()
            if gm.empty:
                st.info("この学校の試合はありません。")
            else:
                first = gm["校1現ID"] == sid
                gm["相手"] = gm["校2"].where(first, gm["校1"])
                gm["相手県"] = gm["校2県"].where(first, gm["校1県"])
                gm["自得点"] = gm["得点1"].where(first, gm["得点2"])
                gm["相手得点"] = gm["得点2"].where(first, gm["得点1"])
                gm["結果"] = (gm["自得点"] > gm["相手得点"]).map({True: "○", False: "●"})
                gm["スコア"] = gm["自得点"].astype(str) + "-" + gm["相手得点"].astype(str)
                gy = sorted(gm["年"].unique(), reverse=True)
                sel_y = st.multiselect("年", gy, default=gy, key="gm_years")
                gm = gm[gm["年"].isin(sel_y)].sort_values(
                    ["日付", "ラウンド順"], ascending=[False, False])
                st.caption(f"{len(gm)}試合 / {int((gm['結果'] == '○').sum())}勝"
                           f"{int((gm['結果'] == '●').sum())}敗")
                st.dataframe(gm[["日付", "大会名", "ラウンド", "結果", "スコア",
                                 "相手", "相手県"]], hide_index=True)

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
        want = ["優勝", "準優勝", "ベスト4", "ベスト8"]
        sk = sp[sp["大会種別"].isin(pk) & sp["結果"].isin(want)]
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
                rows.append(dict(
                    最終戦日=str(d["最終戦日"].max()), 年=y, 大会種別=k, 大会名=nm,
                    優勝=w1[0] if w1 else "", 準優勝=w2[0] if w2 else "",
                    b4=lst("ベスト4"), b8=lst("ベスト8")))
            tb = expand(rows, {"b4": "ベスト4-", "b8": "ベスト8-"})
            tb = tb.sort_values("最終戦日", ascending=not order_new)
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
                ["最終戦日", "大会ID"], ascending=not order_new)
            st.caption("黄色の太字の行は全国大会です。")
            cols2 = ["最終戦日", "年", "大会種別", "大会名", "校名", "結果",
                     "最終ラウンド", "試合数", "勝", "敗"]
            st.dataframe(hp[cols2].reset_index(drop=True).style.apply(hl, axis=1),
                         hide_index=True)

# ---------- 5. 大会結果 ----------
with tabs[4]:
    if stt is None or tms is None:
        st.warning("school_tournament.csv / tournament_master.csv がありません。")
    else:
        kinds_all = ["夏の甲子園", "選抜", "神宮大会", "春季地区大会", "秋季地区大会",
                     "春季県大会", "夏の地方大会", "秋季県大会"]
        kinds_all = [k for k in kinds_all if k in set(stt["大会種別"])]
        kind = st.selectbox("大会種別", kinds_all, key="tn_kind")
        is_pref = kind in ("春季県大会", "夏の地方大会", "秋季県大会")
        is_reg = kind in ("春季地区大会", "秋季地区大会")
        sub = stt[stt["大会種別"] == kind].copy()

        c1, c2 = st.columns(2)
        ys = sorted(sub["年"].unique(), reverse=True)
        ysel2 = c1.multiselect("年", ys, default=ys, key="tn_years")
        sub = sub[sub["年"].isin(ysel2)]

        if is_pref:
            pl = ["すべて"] + sorted(sub["都道府県"].dropna().unique())
            pp = c2.selectbox("都道府県", pl, key="tn_pref")
            if pp != "すべて":
                sub = sub[sub["都道府県"] == pp]
        elif is_reg:
            # 大会ごとの地区 = 出場校の地区の最頻値
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
                if is_pref:
                    return str(x["校名"])
                return str(x["校名"]) + "(" + str(x["都道府県"]) + ")"

            def lst(res):
                return [lab(x) for _, x in d[d["結果"] == res].iterrows()]
            w1 = lst("優勝")
            w2 = lst("準優勝")
            row = dict(年度=y, 大会名=nm)
            if is_pref:
                row["都道府県"] = str(d["都道府県"].iloc[0])
            if is_reg:
                row["地区"] = str(d["大会地区"].iloc[0])
            row.update(優勝=w1[0] if w1 else "", 準優勝=w2[0] if w2 else "",
                       b4=lst("ベスト4"), b8=lst("ベスト8"))
            row["_id"] = tid
            rows.append(row)

        if not rows:
            st.info("該当なし")
        else:
            keys = {"b4": "ベスト4-", "b8": "ベスト8-"}
            tb = expand(rows, keys).sort_values(["年度", "_id"],
                                               ascending=[False, True])
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
                                     hide_index=True)