import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

# ── 1. Load & clean ──────────────────────────────────────────────
PATH = "pastry_sales_2026-10-29.xlsx"   # <- change to your file path

raw = pd.read_excel(PATH, sheet_name="Sales Lines")
df = raw[raw["Status"].str.lower() != "voided"].copy()   # drop voided / double entries
print(f"Dropped {len(raw) - len(df)} voided line(s)")

df["Datetime"] = pd.to_datetime(df["Date"].astype(str) + " " + df["Time"].astype(str))
df["Hour"] = df["Datetime"].dt.hour

# Group products into categories (edit keywords to match your menu)
CATEGORIES = {
    "Drinks":   ["coca", "fanta", "sprite", "water", "juice", "soda"],
    "Savory":   ["samosa", "sandwich", "pizza", "quiche"],
    "Bread":    ["baguette", "bread", "loaf"],
    "Sweet":    ["brownie", "cookie", "muffin", "cake", "cinnamon"],
    "Viennoiserie": ["pain", "croissant"],
}
def categorize(name):
    n = name.lower()
    for cat, keys in CATEGORIES.items():
        if any(k in n for k in keys):
            return cat
    return "Other"
df["Category"] = df["Product Name"].apply(categorize)

# ── 2. Headline numbers ──────────────────────────────────────────
orders = df.groupby("Order Id").agg(total=("Total Price", "sum"), items=("Qty", "sum"),
                                    time=("Datetime", "min"))
print(f"Total sales     : {df['Total Price'].sum():,.0f} RWF")
print(f"Orders          : {len(orders)}")
print(f"Items sold      : {df['Qty'].sum()}")
print(f"Avg order value : {orders['total'].mean():,.0f} RWF")
print(f"Avg items/order : {orders['items'].mean():.1f}")

# ── 3. Plots ─────────────────────────────────────────────────────
rwf = mtick.FuncFormatter(lambda x, _: f"{x:,.0f}")
fig, axes = plt.subplots(3, 2, figsize=(15, 16))
fig.suptitle(f"Pastry shop sales – {df['Date'].iloc[0]}", fontsize=16, fontweight="bold")

# a) Top products by revenue
rev = df.groupby("Product Name")["Total Price"].sum().sort_values().tail(10)
ax = axes[0, 0]
rev.plot.barh(ax=ax, color="#d98c4a")
ax.set(title="Top 10 products by revenue (RWF)", ylabel="")
ax.xaxis.set_major_formatter(rwf)
ax.bar_label(ax.containers[0], labels=[f"{v:,.0f}" for v in rev], padding=3, fontsize=8)

# b) Top products by units sold
units = df.groupby("Product Name")["Qty"].sum().sort_values().tail(10)
ax = axes[0, 1]
units.plot.barh(ax=ax, color="#6a994e")
ax.set(title="Top 10 products by units sold", ylabel="")
ax.bar_label(ax.containers[0], padding=3, fontsize=8)

# c) Sales by hour (revenue bars + order count line)
hourly = df.groupby("Hour")["Total Price"].sum()
hourly_orders = df.groupby("Hour")["Order Id"].nunique()
hours = range(hourly.index.min(), hourly.index.max() + 1)   # include empty hours
hourly = hourly.reindex(hours, fill_value=0)
hourly_orders = hourly_orders.reindex(hours, fill_value=0)
ax = axes[1, 0]
ax.bar(hourly.index, hourly.values, color="#4a7fb5")
ax.set(title="Sales by hour", xlabel="Hour of day", ylabel="Revenue (RWF)")
ax.set_xticks(list(hours)); ax.set_xticklabels([f"{h}:00" for h in hours], rotation=45)
ax.yaxis.set_major_formatter(rwf)
ax2 = ax.twinx()
ax2.plot(hourly_orders.index, hourly_orders.values, color="#c0392b", marker="o", label="Orders")
ax2.set_ylabel("Orders"); ax2.legend(loc="upper right")

# d) Cumulative revenue through the day
ax = axes[1, 1]
cum = orders.sort_values("time").set_index("time")["total"].cumsum()
ax.step(cum.index, cum.values, where="post", color="#8e44ad", lw=2)
ax.fill_between(cum.index, cum.values, step="post", alpha=0.15, color="#8e44ad")
ax.set(title="Cumulative revenue", xlabel="Time", ylabel="RWF")
ax.yaxis.set_major_formatter(rwf)
ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%H:%M"))

# e) Revenue by category
cat = df.groupby("Category")["Total Price"].sum().sort_values(ascending=False)
ax = axes[2, 0]
ax.pie(cat, labels=cat.index, autopct="%1.0f%%", startangle=90,
       wedgeprops={"edgecolor": "white"})
ax.set_title("Revenue share by category")

# f) Payment method split (revenue bars, labelled with order counts)
pay_rev = df.groupby("Payment Method")["Total Price"].sum().sort_values(ascending=False)
pay_orders = df.groupby("Payment Method")["Order Id"].nunique().reindex(pay_rev.index)
ax = axes[2, 1]
ax.bar(pay_rev.index, pay_rev.values, color="#e9c46a")
ax.set(title="Revenue by payment method (RWF)", ylabel="RWF")
ax.yaxis.set_major_formatter(rwf)
ax.bar_label(ax.containers[0],
             labels=[f"{v:,.0f}\n({n} orders)" for v, n in zip(pay_rev, pay_orders)],
             padding=3, fontsize=9)
ax.set_ylim(0, pay_rev.max() * 1.18)

for a in list(axes.flat) + [ax2]:
    a.spines[["top", "right"]].set_visible(False)
ax2.spines["right"].set_visible(True)   # keep the right axis of the hourly chart
plt.tight_layout(rect=[0, 0, 1, 0.97])
plt.show()

# ── 4. Extra tables ──────────────────────────────────────────────
print("\nProduct summary")
display(df.groupby("Product Name").agg(units=("Qty", "sum"), revenue=("Total Price", "sum"),
        orders=("Order Id", "nunique")).sort_values("revenue", ascending=False))

print("Biggest orders")
display(orders.sort_values("total", ascending=False).head(5))
