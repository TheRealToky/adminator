import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

# ── 1. Load & clean ──────────────────────────────────────────────
SALES_PATH = "pastry_sales_2026-10-29.xlsx"            # <- change paths if needed
PROD_PATH  = "pastry_production_2026-10-29.xlsx"

sales = pd.read_excel(SALES_PATH, sheet_name="Sales Lines")
sales = sales[sales["Status"].str.lower() != "voided"].copy()      # drop double entries
prod = pd.read_excel(PROD_PATH, sheet_name="Production Lines")

# Match products on a cleaned name so tiny typos/case differences don't break the join
for d in (sales, prod):
    d["key"] = d["Product Name"].str.strip().str.lower()

sold = sales.groupby("key").agg(sold_qty=("Qty", "sum"), sold_value=("Total Price", "sum"),
                                orders=("Order Id", "nunique"))
made = prod.groupby("key").agg(Product=("Product Name", "first"), Category=("Category", "first"),
                               unit_price=("Unit Price (RWF)", "first"),
                               made_qty=("Qty", "sum"), made_value=("Total Value (RWF)", "sum"))

# outer join: also catches products sold but never recorded as produced (and vice versa)
m = made.join(sold, how="outer")
m["Product"] = m["Product"].fillna(sales.groupby("key")["Product Name"].first())
m[["sold_qty", "sold_value", "orders", "made_qty", "made_value"]] = \
    m[["sold_qty", "sold_value", "orders", "made_qty", "made_value"]].fillna(0)

m["sell_through"] = (m["sold_qty"] / m["made_qty"].where(m["made_qty"] > 0)) * 100   # % of produced that sold
m["unsold_qty"] = m["made_qty"] - m["sold_qty"]
m["unsold_value"] = m["made_value"] - m["sold_value"]                                 # RWF left on the shelf
m = m.reset_index(drop=True)

# ── 2. Headline numbers ──────────────────────────────────────────
tot_made, tot_sold = m["made_qty"].sum(), m["sold_qty"].sum()
print(f"Units produced      : {tot_made:,.0f}")
print(f"Units sold          : {tot_sold:,.0f}  ({tot_sold / tot_made:.0%} sell-through)")
print(f"Value produced      : {m['made_value'].sum():,.0f} RWF")
print(f"Value sold          : {m['sold_value'].sum():,.0f} RWF  ({m['sold_value'].sum() / m['made_value'].sum():.0%})")
print(f"Unsold value        : {m['unsold_value'].sum():,.0f} RWF")
never = m[(m["made_qty"] > 0) & (m["sold_qty"] == 0)]
print(f"Produced, 0 sold    : {len(never)} products -> {', '.join(never['Product'])}")
over = m[m["sold_qty"] > m["made_qty"]]
if len(over):
    print(f"\n⚠ Sold MORE than produced (check data / stock carried over): {', '.join(over['Product'])}")

# ── 3. Plots ─────────────────────────────────────────────────────
rwf = mtick.FuncFormatter(lambda x, _: f"{x:,.0f}")
fig, axes = plt.subplots(3, 2, figsize=(15, 18))
fig.suptitle(f"Sales vs production – {sales['Date'].iloc[0]}", fontsize=16, fontweight="bold")

# a) Sell-through ranking (% of produced units that sold)
r = m.dropna(subset=["sell_through"]).sort_values("sell_through")
colors = ["#6a994e" if v >= 60 else "#e9c46a" if v >= 30 else "#c0392b" for v in r["sell_through"]]
ax = axes[0, 0]
ax.barh(r["Product"], r["sell_through"], color=colors)
ax.set(title="Sell-through by product (% of produced units sold)", xlim=(0, 115))
ax.axvline(100, color="grey", ls="--", lw=1)
ax.bar_label(ax.containers[0], labels=[f"{v:.0f}%" for v in r["sell_through"]], padding=3, fontsize=8)
ax.tick_params(axis="y", labelsize=8)

# b) Produced vs sold, units
r = m.sort_values("made_qty")
ax = axes[0, 1]
ypos = range(len(r))
ax.barh([i + 0.2 for i in ypos], r["made_qty"], height=0.4, color="#b8c4d6", label="Produced")
ax.barh([i - 0.2 for i in ypos], r["sold_qty"], height=0.4, color="#4a7fb5", label="Sold")
ax.set_yticks(list(ypos)); ax.set_yticklabels(r["Product"], fontsize=8)
ax.set(title="Produced vs sold (units)"); ax.legend(loc="lower right")

# c) Biggest unsold value (where money is left on the shelf)
r = m.sort_values("unsold_value").tail(10)
ax = axes[1, 0]
ax.barh(r["Product"], r["unsold_value"], color="#c0392b")
ax.set(title="Top 10 unsold value (RWF, at menu price)")
ax.xaxis.set_major_formatter(rwf)
ax.bar_label(ax.containers[0], labels=[f"{v:,.0f}" for v in r["unsold_value"]], padding=3, fontsize=8)

# d) Category: produced vs sold value, with sell-through %
c = m.groupby("Category")[["made_value", "sold_value"]].sum()
c["pct"] = c["sold_value"] / c["made_value"] * 100
c = c.sort_values("made_value", ascending=False)
ax = axes[1, 1]
x = range(len(c))
ax.bar([i - 0.2 for i in x], c["made_value"], width=0.4, color="#b8c4d6", label="Produced value")
ax.bar([i + 0.2 for i in x], c["sold_value"], width=0.4, color="#4a7fb5", label="Sold value")
for i, p in enumerate(c["pct"]):
    ax.text(i + 0.2, c["sold_value"].iloc[i], f"{p:.0f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
ax.set_xticks(list(x)); ax.set_xticklabels(c.index, rotation=20)
ax.yaxis.set_major_formatter(rwf)
ax.set(title="Category: produced vs sold value (RWF, % = sell-through)"); ax.legend()

# e) Scatter: produced vs sold (points under the line = overproduction)
ax = axes[2, 0]
ax.scatter(m["made_qty"], m["sold_qty"], s=60, color="#8e44ad", alpha=0.75)
lim = max(m["made_qty"].max(), m["sold_qty"].max()) + 2
ax.plot([0, lim], [0, lim], "k--", lw=1, label="Sold = produced")
for _, row in m.iterrows():
    if row["made_qty"] >= 10 or row["sold_qty"] >= 5 or row["unsold_value"] > 12000:
        ax.annotate(row["Product"], (row["made_qty"], row["sold_qty"]), fontsize=7,
                    xytext=(4, 3), textcoords="offset points")
ax.set(title="Produced vs sold per product", xlabel="Units produced", ylabel="Units sold",
       xlim=(0, lim), ylim=(0, lim)); ax.legend()

# f) Where the day's production value went: sold / unsold by category
s_u = c[["sold_value"]].copy()
s_u["unsold_value"] = c["made_value"] - c["sold_value"]
ax = axes[2, 1]
s_u.plot.bar(stacked=True, ax=ax, color=["#6a994e", "#c0392b"], rot=20)
ax.set(title="Production value: sold vs unsold by category (RWF)", xlabel="")
ax.yaxis.set_major_formatter(rwf)
ax.legend(["Sold", "Unsold"])

for a in axes.flat:
    a.spines[["top", "right"]].set_visible(False)
plt.tight_layout(rect=[0, 0, 1, 0.97])
plt.show()

# ── 4. Tables ────────────────────────────────────────────────────
cols = ["Product", "Category", "made_qty", "sold_qty", "sell_through", "unsold_qty", "unsold_value"]
show = m[cols].sort_values("sell_through", ascending=False, na_position="last")
print("\nSell-through ranking")
display(show.style.format({"sell_through": "{:.0f}%", "unsold_value": "{:,.0f}",
                           "made_qty": "{:.0f}", "sold_qty": "{:.0f}", "unsold_qty": "{:.0f}"})
        .hide(axis="index"))
