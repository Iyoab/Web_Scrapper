from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import datetime
import warnings
import requests
import pandas as pd
import yaml

# settings
warnings.filterwarnings("ignore")
pd.set_option("display.max_columns", None)

# Load configuration from YAML file
with open("config.yaml", "r") as config_file:
    config = yaml.safe_load(config_file)

# Extract values from the configuration
api_key = config["api_key"]
sender_email = config["email_config"]["sender_email"]
receiver_emails = config["email_config"]["receiver_emails"]
zip_codes_to_check = config["zip_codes_to_check"]
listing_url = config["listing_url"]
password = config["email_config"]["smtp_password"]


def get_listings(api_key, listing_url):
    url = "https://app.scrapeak.com/v1/scrapers/zillow/listing"
    querystring = {
        "api_key": api_key,
        "url": listing_url
    }
    return requests.request("GET", url, params=querystring)


def get_property_detail(api_key, zpid):
    url = "https://app.scrapeak.com/v1/scrapers/zillow/property"
    querystring = {
        "api_key": api_key,
        "zpid": zpid
    }
    return requests.request("GET", url, params=querystring)


def get_zpid(api_key, street, city, state, zip_code=None):
    url = "https://app.scrapeak.com/v1/scrapers/zillow/zpidByAddress"
    querystring = {
        "api_key": api_key,
        "street": street,
        "city": city,
        "state": state,
        "zip_code": zip_code
    }
    return requests.request("GET", url, params=querystring)


# get listings
listing_response = get_listings(api_key, listing_url)
df_listings = pd.json_normalize(listing_response.json()["data"]["cat1"]["searchResults"]["mapResults"])
df_listings = df_listings.dropna(subset=["hdpData.homeInfo.zipcode"])
# Convert data types of 'zipcode' and 'price' columns
df_listings["zipcode"] = df_listings["hdpData.homeInfo.zipcode"].astype(int)
df_listings["price"] = df_listings["hdpData.homeInfo.price"].astype(float)
MIN_PRICE = 10000.0  # Set the minimum price you are interested in
MAX_PRICE = 300000.0  # Set the maximum price you are interested in
# Example of df_filtered
df_filtered = df_listings[df_listings['zipcode'].isin(zip_codes_to_check) & 
                          (df_listings['price'] >= MIN_PRICE) & 
                          (df_listings['price'] <= MAX_PRICE)]

def send_email(subject, body):
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = ", ".join(receiver_emails) 
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP('smtp.office365.com', 587)
    server.starttls()
    server.login(sender_email, password)
    server.sendmail(sender_email, receiver_emails, msg.as_string())
    server.quit()
current_date = datetime.datetime.now().strftime("%Y-%m-%d")
file_name = f"filtered_houses_{current_date}.csv"
df_filtered.to_csv(file_name, index=False)

if not df_filtered.empty:
    # Send an email notification with the properties that match the criteria
    subject = "Houses for Sale Notification"
    body = "These are houses for sale in the zip codes and within the price ranges.\n\n"
    table_string = df_filtered[['address', 'zipcode', 'price']].to_string(index=False)
    body += table_string

    # Add the link to each property in the body
    for _, row in df_filtered.iterrows():
        address = row['address']
        zillow_url = f"https://www.zillow.com{row['detailUrl']}"
        body += f"\n\nAddress: {address}\nLink: {zillow_url}"
    send_email(subject, body)
    print("Email notification sent successfully!")
else:
    print("No properties found matching the criteria.")
