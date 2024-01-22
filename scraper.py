from bs4 import BeautifulSoup as bs
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from time import sleep
from datetime import datetime
import csv
import re

#### CONFIG ####
HEADLESS = True
SKILLBRIDGE_URL = "https://skillbridge.osd.mil/locations.htm"
SKILLBRIDGE_ORG_URL = "https://skillbridge.osd.mil/data/organizationsData.js"
CSV_NAME = f"{datetime.now().isoformat(timespec='minutes').replace(':', '')}.csv"
# Slower computers/internet might need to increase this
LOAD_DRIVER = 5
LOAD_SEARCH = 15
################

def main():
    print(f"Loading browser in the background and initiating search (This should take roughly {LOAD_SEARCH + LOAD_DRIVER} seconds).")
    options = Options()
    if HEADLESS:
        options.add_argument('-headless')
    driver = webdriver.Firefox(options=options)
    driver.get(SKILLBRIDGE_URL)
    sleep(LOAD_DRIVER)       
    element = driver.find_element(By.ID, 'keywords')
    element.send_keys(Keys.ENTER)
    sleep(LOAD_SEARCH)

    # There should be only one of these classes at the 
    # bottom left corner of the table
    total_entries = driver.find_element(By.CLASS_NAME, 'dataTables_info').text
    # removing the first part of string, then second half
    # taking out the comma to allow for the int() to not error
    # on values over 999. RE could be used here... but seems
    # overkill for a single value like this
    total_entries = int(total_entries.split("of ")[1].split(" entries")[0].replace(",", ""))
    
    print("Gathering data... this will be a few minutes...")

    # Using as a "tracker" to show some basic progression bar
    progress = 0
    while True:
        next_button = driver.find_element(By.ID, 'location-table_next')
        next_button_class = next_button.get_attribute("class")
        getCurrentTable(driver)
        if 'disabled' not in next_button_class:
            next_button.send_keys(Keys.ENTER)
        else:
            break
        # Used to show the script is still running, as it can take
        # some time to cycle through all the pages
        if progress % 10 == 0:
            print('|', end="", flush=True)
            progress += 1
        else:
            progress += 1

    # Value is used to verify data matches expected entries
    # pulled at the beginning of the script
    check_length = len(job_data)

    headers = ["Partner/Program", 
            "Service","City",
            "State",
            "Zip",
            "Duration of Training",
            "Employer POC",
            "POC Email","Cost",
            "Closest Installation",
            "Op by State",
            "Delivery Method",
            "Target MOCs",
            "Other (Pre-Req?)",
            "Other (Eligibility?)",
            "Job Description",
            "Summary Description",
            "Job Family",
            "MOU Organization","Lat","Long"]
    job_data.insert(0, headers)

    # Getting another URL and then parsing that before writing to CSV
    driver.get(SKILLBRIDGE_ORG_URL)
    soup = bs(driver.page_source, features="html.parser")
    # js file being parsed when loaded in a browser has <pre> tags
    data = soup.find('pre')

    ############# Added this after the original script to include the organizations ########
    # Find where the js dict starts
    start = data.text.find("PROGRAM:")
    # Reverse search to find the last data point
    end = len(data.text) - data.text[::-1].find(",}")
    trimmed_data = data.text[start:end-3].strip()
    split_data = trimmed_data.split("},\n    {")

    organizations = []
    for item in split_data:
        #job = re.split('PROGRAM: |, URL: |, OPPORTUNITY_TYPE: |, DELIVERY_METHOD: |, PROGRAM_DURATION: |, STATES: |, NATIONWIDE: |, ONLINE: |, COHORTS: |, JOB_FAMILY: |, LOCATION_DETAILS_AVAILABLE: ', item)[1:]
        job = re.split('PROGRAM:|URL:|OPPORTUNITY_TYPE:|DELIVERY_METHOD:|PROGRAM_DURATION:|STATES:|NATIONWIDE:|ONLINE:|COHORTS:|JOB_FAMILY:|LOCATION_DETAILS_AVAILABLE:', item)[1:]
        program = job[0].strip()[1:-2]
        url = job[1].strip()[1:-2]
        op_type = job[2].strip()[1:-2]
        delivery_method = job[3].strip()[1:-2]
        duration = job[4].strip()[1:-2]
        states = job[5].strip()[1:-2]
        nation_wide = job[6].strip()[1:-2]
        online = job[7].strip()[1:-2]
        cohorts = job[8].strip()[1:-2]
        job_family = job[9].strip()[1:-2]
        loc_detail_avail = job[10].strip()[1:-2]
        line = [program,'','','','',duration,url,url,'','',states,delivery_method,'',op_type,'','','',job_family,'','','']
        #line = f"{program},'','','','',{duration},{url},{url},'','',{states},{delivery_method},'','{op_type}','','','','{job_family}','','',''"
        organizations.append(line)

    final_job_list = job_data + organizations
    #######################################################################################

    with open(CSV_NAME, 'w', encoding="utf-8", newline='') as file:
        writer = csv.writer(file)
        writer.writerows(final_job_list)
    
    if check_length == total_entries:
        print("Success")
    else:
        print("Complete, but the exact entries created do not match the total entries expected.")
    
    driver.close()

def getCurrentTable(driver):
    soup = bs(driver.page_source, features="html.parser")
    # Open table, find the body (tbody) and read any row (rw) 
    table = soup.find('table', attrs={'id':'location-table'})
    table_body = table.find('tbody')
    rows = table_body.find_all('tr')

    for row in rows:
        cols = row.find_all('td')
        
        # Each entry has a button with an onclick
        # method in it that stores the zip
        button = str(row.find_all('button'))
        if 'onclick' in button:
            # Finds the location start, then cuts out the values
            # to then split them up... might be a more elegant way
            # to do this, but it works reliabily
            values = button.split("ShowPin(")[1].split(")' style=")[0]
            values = values.split(",")

            lat = values[0]
            long = values[1]
            city = values[2].strip("\"")
            state = values[3].strip("\"")
            # Using try as some lacking zip values cause errors
            try:
                zip = values[4].strip("\"")
            except:
                zip = ""

        # Need to remove the \n from text inputs or it ruins
        # the output/storage in csv. Truncates the response
        cols_data = [ele.text.replace("\n", "") for ele in cols]

        # If values are above 32767 in a cell, it will flow over
        # and mess with results.
        for i,_ in enumerate(cols_data):
            if len(cols_data[i]) > 32000:
                cols_data[i] = cols_data[i][:32000] + "... Value is too long, please visit https://skillbridge.osd.mil for more information"

        # This removes the "headers" in the table when there 
        # are multiple from a company.
        if len(cols_data) > 3:
            # Check city and state, then add zip into data
            # Just an extra check, so the zip matches up
            if city == cols_data[3] and state == cols_data[4]:
                cols_data.insert(5, zip)
            # to normalize data, if the info didn't match and/or a zip
            # wasn't available, still make sure to add the "column"
            else:
                cols_data.insert(5, "")

            # Remove first column (blank/not needed)
            cols_data.pop(0)
            # Not entirely sure I will ever use these values
            # but didn't want to toss them out
            cols_data.append(lat)
            cols_data.append(long)
            # Add the job to the overall data
            job_data.append(cols_data) 

# This was added to show orgs that don't have specific listings
def getOrganizations(driver):
    soup = bs(driver.page_source, features="html.parser")
    data = soup.find('pre')

    # Find where the js dict starts
    start = data.text.find("PROGRAM:")
    # # Reverse search to find the last data point
    end = len(data.text) - data.text[::-1].find(",}")
    trimmed_data = data.text[start:end-3].strip()
    split_data = trimmed_data.split("},\n    {")

    split_jobs = []
    for item in split_data:
        #job = re.split('PROGRAM: |, URL: |, OPPORTUNITY_TYPE: |, DELIVERY_METHOD: |, PROGRAM_DURATION: |, STATES: |, NATIONWIDE: |, ONLINE: |, COHORTS: |, JOB_FAMILY: |, LOCATION_DETAILS_AVAILABLE: ', item)[1:]
        job = re.split('PROGRAM:|URL:|OPPORTUNITY_TYPE:|DELIVERY_METHOD:|PROGRAM_DURATION:|STATES:|NATIONWIDE:|ONLINE:|COHORTS:|JOB_FAMILY:|LOCATION_DETAILS_AVAILABLE:', item)[1:]
        program = job[0].strip()[1:-2]
        url = job[1].strip()[1:-2]
        op_type = job[2].strip()[1:-2]
        delivery_method = job[3].strip()[1:-2]
        duration = job[4].strip()[1:-2]
        states = job[5].strip()[1:-2]
        nation_wide = job[6].strip()[1:-2]
        online = job[7].strip()[1:-2]
        cohorts = job[8].strip()[1:-2]
        job_family = job[9].strip()[1:-2]
        loc_detail_avail = job[10].strip()[1:-2]
        line = [program,'','','','',duration,url,url,'','',states,delivery_method,'',op_type,'','','',job_family,'','','']
        #line = f"{program},'','','','',{duration},{url},{url},'','',{states},{delivery_method},'','{op_type}','','','','{job_family}','','',''"
        split_jobs.append(line)

    return split_jobs


if __name__ == "__main__":
    job_data = []
    main()
