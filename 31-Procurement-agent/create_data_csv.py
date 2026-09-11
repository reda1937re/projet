import csv

# Data for each product/vendor combo
data = [
    {
        "Product Name": "Office Furniture", 
        "Vendor Name": "Indus Office", 
        "Product Title": "Mobilier de Bureau Casablanca & Maroc", 
        "Price": "", 
        "Currency": "", 
        "Bulk Discounts or Deals": "", 
        "Vendor Website": "https://indusoffice.com/", 
        "Short Product Description": "Leaders in office furniture offering personalized solutions for ergonomic and elegant workspaces.", 
        "Minimum Order Quantity": "", 
        "Shipping Time": "", 
        "Vendor Location": "Casablanca"
    },
    {
        "Product Name": "Laptops", 
        "Vendor Name": "A3 Informatique", 
        "Product Title": "Matériel Informatique Maroc", 
        "Price": "", 
        "Currency": "", 
        "Bulk Discounts or Deals": "", 
        "Vendor Website": "https://www.a3informatique.ma/", 
        "Short Product Description": "Offers new and used laptops, multimedia devices, and a wide range of IT equipment.", 
        "Minimum Order Quantity": "", 
        "Shipping Time": "", 
        "Vendor Location": "Casablanca"
    },
    {
        "Product Name": "Office Furniture", 
        "Vendor Name": "Mobilier Bureau Pro (MBP)", 
        "Product Title": "Professional Office Furniture", 
        "Price": "", 
        "Currency": "", 
        "Bulk Discounts or Deals": "", 
        "Vendor Website": "https://b2bmap.com/mobilier-bureau-pro-mbp", 
        "Short Product Description": "Provides designs and sells professional-grade furniture with a focus on comfort and sustainability.", 
        "Minimum Order Quantity": "", 
        "Shipping Time": "", 
        "Vendor Location": "Casablanca"
    }
]

# Define the CSV file name
file_name = 'data.csv'

# Define the CSV headers
headers = [
    "Product Name", "Vendor Name", "Product Title", "Price", "Currency", 
    "Bulk Discounts or Deals", "Vendor Website", "Short Product Description", 
    "Minimum Order Quantity", "Shipping Time", "Vendor Location"
]

# Write data to CSV file
with open(file_name, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.DictWriter(file, fieldnames=headers)
    writer.writeheader()
    for entry in data:
        writer.writerow(entry)

print("CSV file created successfully.")