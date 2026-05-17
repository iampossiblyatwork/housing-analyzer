import json
import rentcast

# --- Example: look up a property ---
# props = rentcast.get_properties(address="5500 Grand Lake Dr, San Antonio, TX, 78244")
# print(json.dumps(props, indent=2))

# --- Example: rent estimate ---
# estimate = rentcast.get_rent_estimate(address="5500 Grand Lake Dr, San Antonio, TX, 78244")
# print(json.dumps(estimate, indent=2))

# --- Example: market stats for a zip code ---
# stats = rentcast.get_market_stats("78244")
# print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    print("RentCast client ready. Uncomment an example above to try it out.")
