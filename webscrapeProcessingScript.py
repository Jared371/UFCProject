import requests
from bs4 import BeautifulSoup
import csv
import re
from collections import OrderedDict
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
# Initialize global variables
failData = []
finalFailData = []
rawData = []
finalData = []

# Initialize cache for birthdays
birthday_cache = OrderedDict()

# Define the exit key
exitKey = 'ufc 27:'
exitDate = ''
rawCount = 0
rawFailcount = 0
finalCount = 0
finalFailCount = 0

# Define CSV headers
finalHeader = ["FightID", "Fighter", "Opponent", "FighterAge", "OpponentAge", "Outcome", "WeightClass", "GenderBool", "ChampBoutBool"]
rawHeader = ["Event", "Date", "WinningFighter", "LosingFighter", "Method", "WeightClass", "WinningFighterBirthday", "LosingFighterBirthday", "ChampBoutBool", "GenderBool"]

# Create a session object
session = requests.Session()

# Define a retry strategy
retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

def retFighterBooleans(url):
    response = session.get(url, timeout=10)
    fighter_soup = BeautifulSoup(response.text, 'html.parser')
    events_table = fighter_soup.select_one('.b-fight-details__fight-title')
    titleBool = False
    genderBool = False
    if events_table and events_table.get_text(strip=True).lower().find('title') != -1:
        titleBool = True
    if events_table and events_table.get_text(strip=True).lower().find('women') != -1:
        genderBool = True
    return titleBool, genderBool

def findMonth(text):
    print(f"Checking for month in: '{text}'")
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
              "January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]
    month_pattern = re.compile('|'.join(months), re.IGNORECASE)
    match = month_pattern.search(text)
    found = match is not None
    print(f"Month found: {found}")  # Debug statement
    return found

def splitOnMonth(text):
    months = ["January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]
    
    # Create a regex pattern to match the month names
    month_pattern = re.compile(r'\b(' + '|'.join(months) + r')\b')
    match = month_pattern.search(str(text))

    if match:
        before_month = text[:match.start()].strip()
        from_month_onward = text[match.start():].strip()
        return before_month, from_month_onward
    return '', ''

def writeToCSV(rows, header, file_path):
    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as file: # Opens/Creates and wipes file
            writer = csv.writer(file)
            writer.writerow(header)  # Write the header
            for row in rows:
                writer.writerow(row)  # Write the row
                print("CSV row written: ", row)
    except Exception as e:
        print(f"Error writing to CSV {file_path}: {e}")

def getFighterBirthday(fighter_url):
    # Check if the URL is already in the cache
    if fighter_url in birthday_cache:
        # Move the recently accessed URL to the end to maintain LRU order
        birthday_cache.move_to_end(fighter_url)
        print(f"1) Birthday retrieved from cache for URL: {fighter_url}")
        return birthday_cache[fighter_url]

    # If not in cache, fetch the birthday from the website
    try:
        print(f"2) Fetching birthday from URL: {fighter_url}")
        response = session.get(fighter_url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        birthday_element = soup.select_one('div.b-list__info-box:nth-child(1) > ul:nth-child(1) > li:nth-child(5)')
        if birthday_element:
            birthday = birthday_element.get_text(strip=True).replace('DOB:', '').strip()
            # Check if we need to remove the least recently used item before adding new item
            if len(birthday_cache) >= 750:
                removed_url, removed_birthday = birthday_cache.popitem(last=False)  # Remove the oldest item
                print(f"Removed oldest birthday from cache: {removed_url}, Birthday: {removed_birthday}")
            birthday_cache[fighter_url] = birthday  # Cache the new birthday
            print(f"Birthday {birthday} cached for URL: {fighter_url}")
            print(f"Cache size after addition: {len(birthday_cache)}")  # Current size of the cache
            return birthday
    except requests.exceptions.RequestException as e:
        print(f"Error fetching birthday for {fighter_url}: {e}")
    return ''

def processFight(FightData, event, date):
    global rawCount, rawFailcount
    rowData = [None] * 10
    rowData[0] = str(event)
    rowData[1] = str(date)
    fight_cols = [ele.get_text(" ", strip=True) for ele in FightData.find_all('td')]
    
    if fight_cols:
        fighter_links = FightData.find_all('a', href=True)
        
        # Handle No Contest case
        if len(fighter_links) >= 4 and (fighter_links[1].get_text(strip=True).lower() == 'nc' or fighter_links[2].get_text(strip=True).lower() == 'nc'):
            rowData[2], rowData[3] = fighter_links[2].get_text(strip=True), fighter_links[3].get_text(strip=True)
            rowData[4], rowData[5] = f"{fight_cols[7].strip()}:No Contest", fight_cols[6].strip()
            fighter_links = [a['href'] for a in FightData.find_all('a') if a.get('href')]
            if len(fighter_links) >= 4:
                rowData[6], rowData[7] = getFighterBirthday(fighter_links[2]), getFighterBirthday(fighter_links[3])
                rowData[8], rowData[9] = retFighterBooleans(fighter_links[0])
        
        # Handle Draw case
        elif len(fighter_links) >= 4 and (fighter_links[1].get_text(strip=True).lower() == 'draw' or fighter_links[2].get_text(strip=True).lower() == 'draw'):
            rowData[2], rowData[3] = fighter_links[2].get_text(strip=True), fighter_links[3].get_text(strip=True)
            rowData[4], rowData[5] = f"{fight_cols[7].strip()}:Draw", fight_cols[6].strip()
            fighter_links = [a['href'] for a in FightData.find_all('a') if a.get('href')]
            if len(fighter_links) >= 4:
                rowData[6], rowData[7] = getFighterBirthday(fighter_links[2]), getFighterBirthday(fighter_links[3])
                rowData[8], rowData[9] = retFighterBooleans(fighter_links[0])
        
        # Handle regular case
        elif len(fighter_links) >= 3:
            rowData[2], rowData[3] = fighter_links[1].get_text(strip=True), fighter_links[2].get_text(strip=True)
            rowData[4], rowData[5] = fight_cols[7].strip(), fight_cols[6].strip()
            fighter_links = [a['href'] for a in FightData.find_all('a') if a.get('href')]
            if len(fighter_links) >= 3:
                rowData[6], rowData[7] = getFighterBirthday(fighter_links[1]), getFighterBirthday(fighter_links[2])
                rowData[8], rowData[9] = retFighterBooleans(fighter_links[0])
        
        # Add to rawData or failData based on completeness
        if all(rowData[:8]) and findMonth(rowData[6]) and findMonth(rowData[7]):
            rawCount += 1
            rawData.append(rowData)
            print(f'{rowData}\nFights WebScraped : {rawCount}\n')
        else:
            print("\n-----Fight Failed to WebScrape-----\n")
            rawFailcount += 1
            failData.append(rowData)
            print(f'\n{rowData}\nFights Failed : {rawFailcount}')
            print("\n---------------\n")


def webScrapeRawData():
    print("\nWebScrape Started\n")
    url = 'http://www.ufcstats.com/statistics/events/completed?page=all'
    #url = 'http://www.ufcstats.com/statistics/events/completed?page=27'
    response = session.get(url, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    events_table = soup.select_one('.b-statistics__table-events')
    rawCount = 0
    rawFailcount = 0
    
    if events_table:
        print("[Event, Date, WinningFighter, LosingFighter, Method, WeightClass, WinningFighterBirthday, LosingFighterBirthday, ChampBoutBool, GenderBool]\n")
        rows = events_table.find_all('tr')
        
        for row in rows:
            cols = [ele.get_text(" ", strip=True) for ele in row.find_all('td')]
            if cols:
                result = splitOnMonth(cols[0])
                if str(result[0]).lower().find(exitKey.lower()) != -1:
                    break
                link = row.find('a', href=True)
                if link:
                    event_url = link['href']
                    event_response = session.get(event_url, timeout=10)
                    event_soup = BeautifulSoup(event_response.text, 'html.parser')
                    fight_event_table = event_soup.select('.b-fight-details__table')
                    fight_rows = fight_event_table[0].find_all('tr')
                    for fight_row in fight_rows:
                        processFight(fight_row, result[0].strip(), result[1].strip())
        print("\nWebScrape done!\n")
    else:
        print("\nEvent table not found on page\n")
    print(f"Fights Processed : {rawCount}\nFights Failed : {rawFailcount}\n")

def calculateAge(birthday, event_date):
    print(f"Calculating age with birthday: {birthday} and event_date: {event_date}")  # Debug statement
    birth_date = datetime.strptime(birthday, "%b %d, %Y")
    event_date = datetime.strptime(event_date, "%B %d, %Y")
    age = event_date.year - birth_date.year - ((event_date.month, event_date.day) < (birth_date.month, birth_date.day))
    print(age)
    return age

def processRawData():
    global finalCount, finalFailCount
    finalCount = 0
    finalFailCount = 0
    id = 1
    for fight in rawData:
        event_date_str = fight[1]
        processedFight = [None] * 9
        winner_name = fight[2]
        winner_birthday = fight[6]
        loser_name = fight[3]
        loser_birthday = fight[7]
        
        # Process Fight
        processedFight[0] = id
        processedFight[1] = winner_name
        processedFight[2] = loser_name
        processedFight[3] = calculateAge(winner_birthday, event_date_str) if winner_birthday else None
        processedFight[4] = calculateAge(loser_birthday, event_date_str) if loser_birthday else None
        processedFight[5] = 1
        processedFight[6] = fight[5]
        processedFight[7] = fight[9]
        processedFight[8] = fight[8]

        if all(processedFight[:4]):
            finalData.append(processedFight.copy())
            finalCount += 1
            print(f'{processedFight}\nFighter Data Processed : {finalCount}\n')
        else:
            print("\n-----Fighter Data Failed to Process-----\n")
            finalFailCount += 1
            finalFailData.append(processedFight.copy())
            print(f'\n{processedFight}\nFights Failed : {finalFailCount}')
            print("\n---------------\n")
        processedFight = [None] * 9

        # Process Fight
        processedFight[0] = id
        processedFight[1] = loser_name
        processedFight[2] = winner_name
        processedFight[3] = calculateAge(loser_birthday, event_date_str) if loser_birthday else None
        processedFight[4] = calculateAge(winner_birthday, event_date_str) if winner_birthday else None
        processedFight[5] = 0
        processedFight[6] = fight[5]
        processedFight[7] = fight[9]
        processedFight[8] = fight[8]

        if all(processedFight[:4]):
            finalData.append(processedFight.copy())
            finalCount += 1
            print(f'{processedFight}\nFighter Data Processed : {finalCount}\n')
        else:
            print("\n-----Fighter Data Failed to Process-----\n")
            finalFailCount += 1
            finalFailData.append(processedFight.copy())
            print(f'\n{processedFight}\nFights Failed : {finalFailCount}')
            print("\n---------------\n")
        id += 1

    print("\nFighter Data Finished being Processed!\n")
    print(f"Fighter Data Processed : {finalCount}\nFighter Data Failed : {finalFailCount}\n")

def main():
    webScrapeRawData()
    processRawData()

    if rawData:
        file_path = 'C:\\Users\\Jared\\Desktop\\UFCRawData.csv'
        writeToCSV(rawData, rawHeader, file_path)
    else:
        print("No Data In rawData\n")
    if failData:
        file_path = 'C:\\Users\\Jared\\Desktop\\UFCFailedRawData.csv'
        writeToCSV(failData, rawHeader, file_path)
    else:
        print("No Data In failData\n")
    if finalData:
        file_path = 'C:\\Users\\Jared\\Desktop\\UFCData.csv'
        writeToCSV(finalData, finalHeader, file_path)
    else:
        print("No Data In finalData\n")
    if finalFailData:
        file_path = 'C:\\Users\\Jared\\Desktop\\UFCFailedData.csv'
        writeToCSV(finalFailData, finalHeader, file_path)
    else:
        print("No Data In finalFailData\n")

    print("\nCSV Files are Done!\n")
    print(f"Fights WebScraped : {rawCount}\nFights Failed : {rawFailcount}\n")
    print(f"Fighter Data Processed : {finalCount}\nFighter Data Failed : {finalFailCount}\n")
    
if __name__ == "__main__":
    main()