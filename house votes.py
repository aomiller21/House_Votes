import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime
import re  # Import regex for cleaning "Page" and numbers

# Base URL of the page to scrape
base_url = "https://clerk.house.gov/Votes/MemberVotes"

# Headers to mimic a browser request
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Prepare to store all vote data
all_votes = []

def scrape_votes():
    global all_votes  # Ensure the global variable is updated
    all_votes = []  # Reset the votes list for each run
    page = 1
    last_page = False  # Flag to track if we are on the last page
    try:
        while True:
            # Construct the URL with the current page number
            url = f"{base_url}/?page={page}"
            print(f"Fetching page {page}...")

            # Fetch the page
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"Failed to fetch page {page}: {response.status_code}")
                print("Stopping scraping due to a failed request.")
                return  # Exit the function

            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all vote containers
            vote_containers = soup.find_all('div', class_='role-call-vote')

            # Debug: Print the length of vote_containers to verify
            print(f"Page {page}: Found {len(vote_containers)} vote containers.")

            # If the number of vote containers is less than 10, set the last_page flag
            if len(vote_containers) < 10:
                if last_page:  # If we are already on the last page, stop scraping
                    print(f"Page {page} has fewer than 10 vote containers. Stopping scraping.")
                    break
                last_page = True  # Mark this as the last page

            # Process each vote container
            for vote in vote_containers:
                try:
                    # Extract date and time
                    date_time_div = vote.find('div', class_='first-row row-comment')
                    if date_time_div:
                        date_time_text = date_time_div.get_text(strip=True)
                        date_str = date_time_text.split('|')[0].strip()
                        vote_date = datetime.strptime(date_str, "%b %d, %Y, %I:%M %p").strftime("%b %d, %Y")
                    else:
                        vote_date = "N/A"

                    # Extract roll call number
                    roll_call_number = vote.find('a', string="View Details")['href'].split('/')[-1]  # Extract roll call number

                    # Extract vote tally using aria-label
                    aye_p = vote.find('p', attrs={'aria-label': lambda x: x and ("aye" in x.lower() or "yea" in x.lower())})
                    no_p = vote.find('p', attrs={'aria-label': lambda x: x and ("no" in x.lower() or "nay" in x.lower())})

                    aye = aye_p['aria-label'].split(',')[-1].strip() if aye_p else "0"
                    no = no_p['aria-label'].split(',')[-1].strip() if no_p else "0"

                    tally = f"{aye}-{no}"

                    # Construct the link manually
                    year = datetime.now().year  # Use the current year
                    roll_call_href = f"https://clerk.house.gov/Votes/{year}{roll_call_number}"

                    # Clean the link and roll call number
                    roll_call_href = roll_call_href.replace("?", "").replace("=", "")
                    if roll_call_href.count(str(year)) > 1:
                        roll_call_href = roll_call_href.replace(f"{year}{year}", f"{year}")

                    # Remove "Page" and any number following it from the end of the link
                    roll_call_href = re.sub(r"Page\d+$", "", roll_call_href, flags=re.IGNORECASE)

                    # Ensure no unwanted characters in Column 1
                    roll_call_number = roll_call_number.replace("?", "").replace("=", "")

                    # Remove "Page" and any number following it until a space or parenthesis
                    roll_call_number = re.sub(r"Page\d+[\s\)]*", "", roll_call_number, flags=re.IGNORECASE)

                    # Ensure the year is not located before the vote tally
                    if str(year) in roll_call_number:
                        roll_call_number = roll_call_number.replace(str(year), "")

                    # Column 1: [Roll Call Number (Tally)](Link)
                    column_1 = f"[{roll_call_number.strip()} ({tally})]({roll_call_href.strip()})"

                    # Extract bill number and hyperlink
                    bill_number_a = vote.find_all('a')
                    if len(bill_number_a) > 1:
                        bill_number = bill_number_a[1].get_text(strip=True)
                        bill_link = bill_number_a[1]['href'] if bill_number_a[1].has_attr('href') else "N/A"
                        # Format Column 4 as "[Bill Number](Link)"
                        column_4 = f"[{bill_number}]({bill_link})"
                    else:
                        column_4 = "N/A"

                    # Extract the full text of the vote
                    vote_text = vote.get_text(strip=True)

                    # Extract Vote Question
                    vote_question = ""
                    if "Vote Question:" in vote_text:
                        vote_question_start = vote_text.find("Vote Question:") + len("Vote Question:")
                        vote_question_end = vote_text.find("Bill", vote_question_start)
                        vote_question_end = vote_question_end if vote_question_end != -1 else vote_text.find("Author", vote_question_start)
                        vote_question = vote_text[vote_question_start:vote_question_end].strip()

                    # Extract Bill Title & Description or Author
                    bill_title_description_or_author = ""
                    if "Bill Title & Description:" in vote_text:
                        bill_start = vote_text.find("Bill Title & Description:") + len("Bill Title & Description:")
                        bill_end = vote_text.find("Vote Type", bill_start)
                        bill_title_description_or_author = vote_text[bill_start:bill_end].strip()
                    elif "Author:" in vote_text:
                        author_start = vote_text.find("Author:") + len("Author:")
                        author_end = vote_text.find("Vote Type", author_start)
                        bill_title_description_or_author = vote_text[author_start:author_end].strip()

                    # Combine into Column 3
                    combined_description = f"{vote_question} {bill_title_description_or_author}".strip()

                    # Determine status by searching for "Passed" or "Failed" in the vote container
                    if "Passed" in vote_text:
                        status = "Passed"
                    elif "Failed" in vote_text:
                        status = "Failed"
                    else:
                        status = "N/A"  # This should not happen based on your clarification

                    # Structure the vote data
                    vote_data = {
                        "Column 1": column_1,  # Updated column 1 with roll call number, tally, and link
                        "Column 2": status,
                        "Column 3": combined_description,
                        "Column 4": column_4,  # Updated column 4 with hyperlink
                        "Column 5": vote_date
                    }

                    all_votes.append(vote_data)
                except Exception as e:
                    print(f"Error processing vote: {e}")
                    print("Continuing after removing violations.")
                    continue  # Skip to the next vote container

            # Increment the page number
            page += 1
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Stopping scraping due to a critical error.")
        return  # Exit the function

    # Save the data to a CSV file
    print("Saving data to votes.csv...")
    with open('votes.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["Column 1", "Column 2", "Column 3", "Column 4", "Column 5"])
        writer.writeheader()
        writer.writerows(all_votes)
    print(f"Scraped {len(all_votes)} votes across all pages. Data saved to 'votes.csv'.")

# Run the scraping process
scrape_votes()