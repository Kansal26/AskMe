"""Synthetic Data Generator for Beauty & Personal Care E-Commerce.

This module generates clean, realistic, fully synthetic datasets for:
- Products (~150 SKUs)
- Orders (~20,000 transactions across 24 months)
- Returns (~2,000 returned items with reasons)
- Reviews (~3,000 short reviews with ratings)

ALL DATA IS SYNTHETIC and generated deterministically via seed=42.
"""

from __future__ import annotations

import datetime
import random
from pathlib import Path
from typing import Any

import pandas as pd

CATEGORIES: list[str] = [
    "Skincare",
    "Haircare",
    "Bath & Body",
    "Fragrance",
    "Color Cosmetics",
]

BRANDS: list[str] = [
    "GlowBotanica",
    "LuxeAura",
    "PureDerma",
    "VelvetPetal",
    "AuraBotanics",
    "SilkRadiance",
    "DermaBloom",
    "BotanicalBliss",
]

CHANNELS: list[str] = [
    "Amazon",
    "Nykaa",
    "Flipkart",
    "QuickCommerce-Blinkit",
    "QuickCommerce-Zepto",
    "D2C Website",
]

CITIES: list[str] = [
    "Mumbai",
    "Delhi",
    "Bengaluru",
    "Hyderabad",
    "Chennai",
    "Kolkata",
    "Pune",
    "Ahmedabad",
    "Jaipur",
    "Chandigarh",
    "Kochi",
    "Lucknow",
]

RETURN_REASONS: list[str] = [
    "Damaged in transit",
    "Defective/Leaking pump",
    "Wrong item delivered",
    "Allergic reaction",
    "Changed mind",
]

PRODUCT_TEMPLATES: dict[str, list[str]] = {
    "Skincare": [
        "Hydrating Hyaluronic Serum",
        "Vitamin C Radiance Glow Serum",
        "Niacinamide 10% Blemish Toner",
        "Gentle Foaming Cleanser",
        "Barrier Repair Moisturizer",
        "Ceramide Daily Sunscreen SPF 50",
        "Glycolic Acid Exfoliating Toner",
        "Retinol 0.5% Night Recovery Oil",
        "Green Tea Mattifying Gel",
        "Centella Calming Gel Cream",
    ],
    "Haircare": [
        "Argan Oil Restorative Shampoo",
        "Keratin Smooth Intense Conditioner",
        "Rosemary Scalp Stimulating Oil",
        "Biotin Anti-Hairfall Mask",
        "Sulfate-Free Clarifying Cleanser",
        "Bond Repair Leave-in Serum",
        "Onion & Fenugreek Hair Oil",
        "Heat Protectant Styling Spray",
        "Tea Tree Anti-Dandruff Tonic",
        "Curl Defining Flaxseed Cream",
    ],
    "Bath & Body": [
        "Shea Butter Deep Moisture Lotion",
        "Coffee Invigorating Body Scrub",
        "Eucalyptus Uplifting Shower Gel",
        "Coconut Milk Hydrating Body Wash",
        "Vanilla Cashmere Whipped Souffle",
        "Almond Oil Nourishing Body Oil",
        "Lavender Sleep Aromatherapy Wash",
        "Exfoliating Loofah Soap Bar",
        "Peppermint Cooling Foot Cream",
        "Cocoa Butter Stretch Mark Balm",
    ],
    "Fragrance": [
        "Velvet Bloom Eau de Parfum",
        "Golden Amber & Oud Mist",
        "Citrus Breeze Eau de Toilette",
        "Midnight Jasmine Intense Parfum",
        "Smoky Wood & Vetiver Cologne",
        "White Musk Soft Floral Mist",
        "Saffron & Cardamom Noir",
        "Ocean Salt & Driftwood EDC",
        "Sweet Vanilla Orchid Perfume",
        "Bergamot Spark Rollerball",
    ],
    "Color Cosmetics": [
        "Matte Velvet Liquid Lipstick",
        "Luminous Radiant Foundation",
        "Full Coverage Cream Concealer",
        "Volumizing Waterproof Mascara",
        "Precision Felt-Tip Liquid Eyeliner",
        "Soft Tinted Lip & Cheek Balm",
        "Hydrating Dewy Primer",
        "Peach Blossom Powder Blush",
        "Ultra-Fine Setting Powder",
        "Micro-Blade Eyebrow Definer",
    ],
}

POSITIVE_REVIEWS = [
    "Absolutely love this product! Noticeable difference within a week of use.",
    "Great texture, absorbs quickly without feeling greasy. Holy grail item.",
    "Repurchased this for the third time. Highly recommend for daily routine.",
    "Smells heavenly and works exactly as described. Worth every penny.",
    "Delivered fast and packaged securely. My skin feels deeply moisturized.",
]

NEUTRAL_REVIEWS = [
    "It works fine, but took about 3 weeks to see any subtle difference.",
    "Decent quality for the price. Packaging could be slightly improved.",
    "Not bad, but not extraordinary either. Average performance overall.",
    "Scent is a bit strong initially, but disappears after a few minutes.",
]

NEGATIVE_REVIEWS = [
    "Did not suit my sensitive skin, experienced slight redness.",
    "Pump dispenser was defective and leaked inside the box.",
    "Felt too heavy on my skin in humid weather. Would not repurchase.",
    "Expected better results considering the high price tag.",
]


def generate_clean_dataset(
    seed: int = 42,
    num_products: int = 150,
    num_orders: int = 20000,
    num_returns: int = 2000,
    num_reviews: int = 3000,
    start_date: datetime.date = datetime.date(2023, 1, 1),
    end_date: datetime.date = datetime.date(2024, 12, 31),
) -> dict[str, pd.DataFrame]:
    """Generates clean, synthetic e-commerce data for testing and analytics."""
    rng = random.Random(seed)

    # 1. Generate Products (~150 SKUs)
    products_data: list[dict[str, Any]] = []
    sku_counter = 1
    category_cycle = list(CATEGORIES)

    while len(products_data) < num_products:
        cat = category_cycle[(sku_counter - 1) % len(category_cycle)]
        brand = rng.choice(BRANDS)
        template = rng.choice(PRODUCT_TEMPLATES[cat])
        variants = ["Original", "Travel Size", "Refill Pack", "Intense", "Mini", "Value Pack"]
        variant = rng.choice(variants)
        product_name = f"{brand} {template} ({variant})"

        # Realistic price tiers in INR
        mrp_tiers = [299.0, 399.0, 499.0, 699.0, 899.0, 1199.0, 1499.0, 1899.0, 2499.0]
        mrp = rng.choice(mrp_tiers)

        sku = f"SKU-{cat[:3].upper()}-{sku_counter:04d}"
        products_data.append({
            "sku": sku,
            "name": product_name,
            "brand": brand,
            "category": cat,
            "mrp": float(mrp),
        })
        sku_counter += 1

    df_products = pd.DataFrame(products_data)

    # 2. Generate Orders (~20,000 orders)
    num_customers = 3500
    customer_ids = [f"CUST-{i:05d}" for i in range(1, num_customers + 1)]
    # Skew repeat customers: top 20% of customers generate 50% of orders
    customer_weights = [3.0 if i < (num_customers * 0.2) else 0.7 for i in range(num_customers)]

    total_days = (end_date - start_date).days
    sku_list = df_products["sku"].tolist()
    mrp_lookup = dict(zip(df_products["sku"], df_products["mrp"]))

    orders_data: list[dict[str, Any]] = []
    discount_tiers = [0.0, 0.05, 0.10, 0.15, 0.20]
    discount_weights = [0.35, 0.25, 0.20, 0.15, 0.05]

    for i in range(1, num_orders + 1):
        order_id = f"ORD-{2023 + (i % 2)}-{i:06d}"
        cust_id = rng.choices(customer_ids, weights=customer_weights, k=1)[0]

        random_day = rng.randint(0, total_days)
        order_date = start_date + datetime.timedelta(days=random_day)

        sku = rng.choice(sku_list)
        channel = rng.choice(CHANNELS)
        quantity = rng.choices([1, 2, 3, 4], weights=[0.65, 0.22, 0.09, 0.04], k=1)[0]
        mrp = mrp_lookup[sku]
        gross_amount = round(float(quantity * mrp), 2)

        # Discount tier (0%, 5%, 10%, 15%, 20%)
        discount_pct = rng.choices(discount_tiers, weights=discount_weights, k=1)[0]
        discount_amount = round(gross_amount * discount_pct, 2)
        net_amount = round(gross_amount - discount_amount, 2)

        city = rng.choice(CITIES)

        orders_data.append({
            "order_id": order_id,
            "customer_id": cust_id,
            "order_date": order_date.strftime("%Y-%m-%d"),
            "sku": sku,
            "channel": channel,
            "quantity": quantity,
            "gross_amount": gross_amount,
            "discount_amount": discount_amount,
            "net_amount": net_amount,
            "city": city,
        })

    # Sort orders chronologically
    orders_data.sort(key=lambda x: x["order_date"])
    df_orders = pd.DataFrame(orders_data)

    # 3. Generate Returns (~2,000 returns sampled from orders)
    # Take a sample of orders for returns (return rate ~10%)
    sample_order_indices = rng.sample(range(len(df_orders)), k=min(num_returns, len(df_orders)))
    returns_data: list[dict[str, Any]] = []
    ret_counter = 1

    for idx in sorted(sample_order_indices):
        order_row = df_orders.iloc[idx]
        ord_date = datetime.date.fromisoformat(order_row["order_date"])
        # Return occurs 2 to 14 days after order date
        return_delay = rng.randint(2, 14)
        return_date = ord_date + datetime.timedelta(days=return_delay)
        reason = rng.choice(RETURN_REASONS)
        # Full or partial refund
        refund_amount = order_row["net_amount"]

        returns_data.append({
            "return_id": f"RET-{ret_counter:06d}",
            "order_id": order_row["order_id"],
            "return_date": return_date.strftime("%Y-%m-%d"),
            "reason": reason,
            "refund_amount": float(refund_amount),
        })
        ret_counter += 1

    df_returns = pd.DataFrame(returns_data)

    # 4. Generate Reviews (~3,000 reviews)
    reviews_data: list[dict[str, Any]] = []
    for i in range(1, num_reviews + 1):
        review_id = f"REV-{i:06d}"
        sku = rng.choice(sku_list)
        rating = rng.choices([5, 4, 3, 2, 1], weights=[0.50, 0.25, 0.12, 0.07, 0.06], k=1)[0]

        if rating >= 4:
            text = rng.choice(POSITIVE_REVIEWS)
        elif rating == 3:
            text = rng.choice(NEUTRAL_REVIEWS)
        else:
            text = rng.choice(NEGATIVE_REVIEWS)

        rev_day = rng.randint(0, total_days)
        review_date = start_date + datetime.timedelta(days=rev_day)

        reviews_data.append({
            "review_id": review_id,
            "sku": sku,
            "rating": rating,
            "review_text": text,
            "review_date": review_date.strftime("%Y-%m-%d"),
        })

    reviews_data.sort(key=lambda x: x["review_date"])
    df_reviews = pd.DataFrame(reviews_data)

    return {
        "products": df_products,
        "orders": df_orders,
        "returns": df_returns,
        "reviews": df_reviews,
    }


def save_clean_datasets(
    output_dir: str | Path = "data/clean",
    seed: int = 42,
    num_products: int = 150,
    num_orders: int = 20000,
    num_returns: int = 2000,
    num_reviews: int = 3000,
) -> dict[str, Path]:
    """Generates and writes clean CSV files with synthetic banner headers."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)

    datasets = generate_clean_dataset(
        seed=seed,
        num_products=num_products,
        num_orders=num_orders,
        num_returns=num_returns,
        num_reviews=num_reviews,
    )

    saved_paths: dict[str, Path] = {}
    for name, df in datasets.items():
        file_path = path / f"{name}.csv"
        df.to_csv(file_path, index=False)
        saved_paths[name] = file_path

    return saved_paths


if __name__ == "__main__":
    saved = save_clean_datasets()
    print("Clean datasets generated successfully:")
    for k, v in saved.items():
        print(f"  - {k}: {v}")
