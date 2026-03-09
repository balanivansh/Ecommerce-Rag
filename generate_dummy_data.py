import csv
import random
from datetime import datetime, timedelta

# E-commerce seed data
CATEGORIES = {
    'Electronics': [
        ('Bluetooth Headphones', 'Noise-cancelling wireless headphones with 40h battery.', ['Battery poor', 'Audio static', 'Uncomfortable']),
        ('Smart Watch', 'Fitness tracking smartwatch with heart rate monitor.', ['Sync issues', 'Screen scratch', 'Arrived late']),
        ('Wireless Mouse', 'Ergonomic 2.4GHz wireless mouse.', ['Scroll wheel broken', 'Connectivity drop', 'Too small']),
        ('4K Smart TV', 'Ultra HD LED television with built-in streaming apps.', ['Dead pixels', 'Laggy UI', 'Damaged in transit']),
        ('Gaming Keyboard', 'Mechanical keyboard with RGB lighting.', ['Keycap missing', 'Loud switches', 'Software buggy'])
    ],
    'Apparel': [
        ('Cotton T-Shirt', 'High-quality comfortable printed cotton t-shirt.', ['Shrank after wash', 'Faded color', 'Too loose']),
        ('Denim Jeans', 'Classic straight fit blue jeans.', ['Too tight', 'Zipper broken', 'Stitching bad']),
        ('Winter Jacket', 'Waterproof insulated winter coat.', ['Not warm enough', 'Zipper stuck', 'Too bulky']),
        ('Yoga Pants', 'Stretchy breathable activewear leggings.', ['See-through', 'Poor elastic', 'Pilling fabric']),
        ('Sneakers', 'Casual everyday walking shoes.', ['Uncomfortable', 'Wrong color', 'Scuffed out of box'])
    ],
    'Appliances': [
        ('Espresso Coffee Maker', '15-bar pump espresso machine with automatic milk frother.', ['Defective heating', 'Leaks water', 'Loud pump']),
        ('Drip Coffee Maker', '12-cup programmable drip coffee maker with glass carafe.', ['Carafe cracked', 'Doesn\'t brew hot', 'Tastes plasticy']),
        ('Air Fryer', '5-quart digital air fryer with presets.', ['Basket peels', 'Smells like burning', 'Timer broken']),
        ('Blender', 'High-speed blender for smoothies.', ['Motor burned out', 'Jar cracked', 'Not blending well']),
        ('Robot Vacuum', 'Smart navigation robotic vacuum cleaner.', ['Gets stuck', 'Poor suction', 'Battery dies fast'])
    ],
    'Home & Kitchen': [
        ('Ceramic Plates Set', 'Set of 4 handcrafted ceramic dinner plates.', ['Chipped edge', 'Uneven glaze', 'Shattered in transit']),
        ('Throw Pillow', 'Decorative velvet throw pillow.', ['Flattened quickly', 'Different color', 'Sheds fabric']),
        ('Desk Lamp', 'LED adjustable study lamp with dimming.', ['Bulb flickers', 'Base unstable', 'Switch broken']),
        ('Cotton Bedsheet', 'King size 400TC cotton bedsheet.', ['Rough texture', 'Torn corner', 'Color bled']),
        ('Kitchen Knives', '6-piece stainless steel chef knife block.', ['Dulls fast', 'Handle loose', 'Rusted quickly'])
    ]
}

REVIEWS_GOOD = [
    "Absolutely love this product!",
    "Exceeded my expectations entirely.",
    "Very high quality. Will buy again.",
    "Works perfectly as described.",
    "Great value for the price.",
    "Fast delivery and excellent packaging.",
    "Highly recommended to anyone.",
    "Super smooth and premium feel.",
    "Best purchase I've made this year.",
    "My wife loves it so much!"
]

HINDI_REVIEWS_GOOD = [
    "बहुत बढ़िया प्रोडक्ट है।",
    "क्वालिटी काफी अच्छी है।",
    "पैसे वसूल सामान।",
    "बिल्कुल वैसा ही है जैसा फोटो में था।"
]

REVIEWS_BAD = [
    "Terrible quality, do not buy.",
    "Broke after two days of use.",
    "Customer service was unhelpful when I complained.",
    "Looks cheap in person.",
    "Completely useless and defective.",
    "I regret buying this.",
    "Worst online shopping experience.",
    "Total waste of money."
]

HINDI_REVIEWS_BAD = [
    "एकदम बेकार क्वालिटी है।",
    "पैसे बर्बाद हो गए इसे खरीद कर।",
    "काम ही नहीं कर रहा ठीक से।",
    "डिलीवरी बहुत देर से आई।"
]

STATUS_WEIGHTS = ['Sold', 'Sold', 'Sold', 'Returned', 'Returned', 'In Transit']

# Generate 2000 rows
def generate_csv(filename):
    start_date = datetime(2023, 1, 1)
    
    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Product ID', 'Date', 'Category', 'Product Name', 'Description', 'Stock', 'Status', 'Return Reason', 'Review', 'Rating', 'Language'])
        
        for i in range(1, 2001):
            prod_id = f"P{str(i).zfill(4)}"
            
            # Random date within last year
            days_offset = random.randint(0, 365)
            row_date = (start_date + timedelta(days=days_offset)).strftime("%Y-%m-%d")
            
            # Pick a product
            category = random.choice(list(CATEGORIES.keys()))
            product_info = random.choice(CATEGORIES[category])
            prod_name, desc, defect_reasons = product_info
            
            stock = random.randint(0, 500)
            status = random.choice(STATUS_WEIGHTS)
            
            reason = ""
            review = ""
            rating = 0
            lang = "English"
            
            # 15% chance of being a Hindi review
            use_hindi = random.random() < 0.15 
            
            if status == 'Returned':
                reason = random.choice(defect_reasons)
                rating = random.randint(1, 3)
                if use_hindi:
                    review = random.choice(HINDI_REVIEWS_BAD)
                    lang = "Hindi"
                else:
                    review = random.choice(REVIEWS_BAD)
                    lang = "English"
            elif status == 'In Transit':
                reason = ""
                review = "Waiting for delivery..."
                rating = 0
            else:
                # Sold
                reason = ""
                # Could be 3-5 rating
                rating = random.randint(3, 5)
                
                # Sometime people don't leave reviews
                if random.random() < 0.3:
                    review = ""
                    rating = 0
                else:
                    if rating <= 3:
                        if use_hindi:
                            review = random.choice(HINDI_REVIEWS_BAD)
                            lang = "Hindi"
                        else:
                            review = random.choice(REVIEWS_BAD)
                            lang = "English"
                    else:
                        if use_hindi:
                            review = random.choice(HINDI_REVIEWS_GOOD)
                            lang = "Hindi"
                        else:
                            review = random.choice(REVIEWS_GOOD)
                            lang = "English"
                            
            writer.writerow([prod_id, row_date, category, prod_name, desc, stock, status, reason, review, rating, lang])

if __name__ == "__main__":
    generate_csv('sample_data.csv')
    print("Generated 2000 rows successfully.")
