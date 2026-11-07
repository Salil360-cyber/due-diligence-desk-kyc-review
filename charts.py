"""Report charts for Due Diligence Desk.

Reads the completed review in Due_Diligence_Desk_Solved.xlsx, re-checks the key counts against the
raw inputs in Due_Diligence_Desk_KYC_Data.xlsx, and saves the charts to charts/. Run: python charts.py
"""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

OUT = Path("charts"); OUT.mkdir(exist_ok=True)
BLUE, ORANGE, AQUA, RED, GREY, LIGHT = "#2a78d6", "#eb6834", "#1baf7a", "#d03b3b", "#9a9a95", "#d6d5cf"
INK, INK2, BG = "#0b0b0b", "#52514e", "#fcfcfb"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#c9c8c3", "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK, "figure.facecolor": BG, "axes.facecolor": BG})
NOTE = "Simulated data: 60 fictional corporate clients · report date 1 Oct 2026"

def save(fig, name):
    fig.tight_layout(); fig.savefig(OUT / name, dpi=160, bbox_inches="tight"); plt.close(fig)

S = pd.read_excel("Due_Diligence_Desk_Solved.xlsx", sheet_name=None)
R = pd.read_excel("Due_Diligence_Desk_KYC_Data.xlsx", sheet_name=None)
cr, hits, oc = S["Client_Review"], S["Screening_Hits"], S["Ownership_Chains"]

# ---------- cross-check the solved workbook against the raw inputs
report = pd.Timestamp("2026-10-01")
raw_oc = R["Ownership_Chains"]
eff = raw_oc.L1_Pct * raw_oc.L2_Pct.fillna(1) * raw_oc.L3_Pct.fillna(1)
checks = {
    "documents required": (len(R["Documents_Checklist"]), 326),
    "documents missing": (int((R["Documents_Checklist"].Received == "No").sum()), int(cr.Docs_Missing.sum())),
    "expired IDs": (int((R["People"].ID_Expiry < report).sum()), int(cr.Expired_IDs.sum())),
    "UBOs at 25%": (int((eff >= 0.25).sum()), int(cr.UBO_Count.sum())),
    "indirect UBOs": (int(((eff >= 0.25) & (raw_oc.Layers > 1)).sum()), int(((oc.UBO_Flag == "UBO") & (oc.Layers > 1)).sum())),
    "screening hits": (len(R["Screening_Hits"]), len(hits)),
}
for k, (raw, solved) in checks.items():
    assert raw == solved, f"{k}: raw {raw} vs solved {solved}"
print("Cross-checks passed:", {k: v[0] for k, v in checks.items()})

# ---------- 1. case status (where every client stands)
status = cr.Case_Status.value_counts().sort_index()
owner = {"1": ("Stop", RED), "2": ("Stop", RED), "3": ("Back to RM", GREY), "4": ("Back to RM", GREY),
         "5": ("To Compliance", ORANGE), "6": ("Ready", BLUE)}
fig, ax = plt.subplots(figsize=(8.5, 3.9))
labels = [s.split(". ", 1)[1] for s in status.index][::-1]
cols = [owner[s[0]][1] for s in status.index][::-1]
ax.barh(labels, status.values[::-1], color=cols, height=0.62)
for i, v in enumerate(status.values[::-1]):
    ax.text(v + 0.3, i, str(v), va="center", fontsize=9, color=INK2)
ax.set_xlim(0, 25); ax.set_xlabel("Clients")
ax.legend(handles=[Patch(color=c, label=l) for l, c in [("Ready for approval", BLUE), ("Escalate to Compliance", ORANGE),
                                                        ("Back to RM", GREY), ("Stop", RED)]],
          frameon=False, loc="upper right", fontsize=9)
ax.set_title(f"Case status: {status.iloc[-1]} of 60 clients ready for approval", loc="left", fontsize=11, color=INK)
fig.text(0.01, -0.03, NOTE + " · each client gets the first status that applies, in this order", fontsize=8, color=INK2)
save(fig, "01_case_status.png")

# ---------- 2. issues found in the review
issues = pd.Series({
    "Documents missing": int(cr.Docs_Missing.sum()),
    "Stale proof of address (>90 days)": int(cr.Stale_Docs.sum()),
    "Expired IDs": int(cr.Expired_IDs.sum()),
    "Registry field mismatches": int(cr.Registry_Mismatches.sum()),
    "Entity not active (dissolved)": int((cr.Entity_Status == "NOT ACTIVE").sum()),
    "Clients with no 25% owner": int((cr.UBO_Gap == "Yes").sum()),
    "Cases past the 30-day SLA": int((cr.SLA_Status == "Overdue").sum()),
}).iloc[::-1]
fig, ax = plt.subplots(figsize=(8.5, 3.9))
ax.barh(issues.index, issues.values, color=BLUE, height=0.62)
for i, v in enumerate(issues.values):
    ax.text(v + 0.3, i, str(v), va="center", fontsize=9, color=INK2)
ax.set_xlim(0, 25); ax.set_xlabel("Count")
ax.set_title("What the review found", loc="left", fontsize=11, color=INK)
fig.text(0.01, -0.03, NOTE + f" · {checks['documents required'][0]} required documents, "
         f"{len(S['People'])} people, {len(oc)} ownership chains checked", fontsize=8, color=INK2)
save(fig, "02_issues_found.png")

# ---------- 3. ownership: effective % of every chain vs the 25% UBO line
fig, ax = plt.subplots(figsize=(8.5, 3.6))
groups = [(1, BLUE, "Direct (1 layer)"), (2, ORANGE, "Through 1 holding company"), (3, RED, "Through 2 holding companies")]
vals = [oc.loc[oc.Layers == l, "Effective_Pct"] for l, _, _ in groups]
ax.hist(vals, bins=[i / 20 for i in range(21)], stacked=True, color=[c for _, c, _ in groups],
        label=[f"{lab} ({len(v)})" for (_, _, lab), v in zip(groups, vals)], edgecolor=BG, linewidth=1)
ax.axvline(0.25, color=INK, lw=1.2, ls="--")
n_ubo = int((oc.UBO_Flag == "UBO").sum()); n_ind = checks["indirect UBOs"][1]
ax.text(0.26, ax.get_ylim()[1] * 0.97, f"25% UBO threshold: {n_ubo} chains at or above it ({n_ind} indirect),\n{len(oc) - n_ubo} below it",
        fontsize=8.5, color=INK, va="top", bbox=dict(facecolor=BG, edgecolor="none", pad=1))
ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0%}"); ax.set_xlim(0, 1)
ax.set_xlabel("Effective ownership of the client (% held at each layer multiplied)"); ax.set_ylabel("Ownership chains")
ax.legend(frameon=False, loc="center right", fontsize=9)
ax.set_title(f"{len(oc)} ownership chains traced to identify {n_ubo} UBOs", loc="left", fontsize=11, color=INK)
fig.text(0.01, -0.03, NOTE + " · bars stacked by number of layers; 5% bins", fontsize=8, color=INK2)
save(fig, "03_ownership_chains.png")

# ---------- 4. screening hits by list and disposition
order_d = ["True Match", "False Positive", "Escalate - insufficient info"]
dcol = {"True Match": RED, "False Positive": GREY, "Escalate - insufficient info": ORANGE}
tab = hits.pivot_table(index="List_Type", columns="Disposition", values="Hit_ID", aggfunc="count", fill_value=0)
tab = tab.reindex(columns=order_d, fill_value=0).loc[["Sanctions", "PEP", "Adverse Media"]]
fig, ax = plt.subplots(figsize=(8.5, 3.2))
left = pd.Series(0, index=tab.index)
for d_ in order_d:
    ax.barh(tab.index[::-1], tab[d_][::-1], left=left[::-1], color=dcol[d_], height=0.55,
            label=f"{d_} ({int(tab[d_].sum())})", edgecolor=BG, linewidth=2)
    for i, (l, v) in enumerate(zip(left[::-1], tab[d_][::-1])):
        if v: ax.text(l + v / 2, i, str(v), ha="center", va="center", fontsize=9, color="white" if d_ != "False Positive" else INK)
    left += tab[d_]
ax.set_xlabel("Screening hits"); ax.set_xlim(0, 12)
ax.legend(frameon=False, loc="lower right", fontsize=9)
ax.set_title(f"{len(hits)} screening hits cleared: true match only when date and nationality/country both match",
             loc="left", fontsize=11, color=INK)
fig.text(0.01, -0.04, NOTE + " · a name match alone is not a true match; missing date or nationality = escalate", fontsize=8, color=INK2)
save(fig, "04_screening_hits.png")

# ---------- 5. risk rating by entity type
rorder = ["Low", "Medium", "High", "Prohibited"]
rcol = {"Low": "#a7c8f0", "Medium": "#5b9be0", "High": "#1f5fae", "Prohibited": RED}
rt = pd.crosstab(cr.Entity_Type, cr.Risk_Rating).reindex(columns=rorder, fill_value=0)
rt = rt.loc[rt.sum(axis=1).sort_values().index]
fig, ax = plt.subplots(figsize=(8.5, 3.4))
left = pd.Series(0, index=rt.index)
for r_ in rorder:
    ax.barh(rt.index, rt[r_], left=left, color=rcol[r_], height=0.6, label=f"{r_} ({int(rt[r_].sum())})",
            edgecolor=BG, linewidth=2)
    for i, (l, v) in enumerate(zip(left, rt[r_])):
        if v: ax.text(l + v / 2, i, str(v), ha="center", va="center", fontsize=9, color=INK if r_ == "Low" else "white")
    left += rt[r_]
ax.set_xlabel("Clients"); ax.legend(frameon=False, loc="lower right", fontsize=9)
ax.set_title(f"Risk rating: {int(rt['High'].sum())} clients High risk and sent for EDD", loc="left", fontsize=11, color=INK)
fig.text(0.01, -0.04, NOTE + " · score = country + industry + entity + product + ownership/PEP/media add-ons; sanctions match = Prohibited",
         fontsize=8, color=INK2)
save(fig, "05_risk_by_entity_type.png")
print("Charts saved to", OUT)
