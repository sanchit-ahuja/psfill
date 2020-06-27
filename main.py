import os
import json
import requests
from bs4 import BeautifulSoup  # type: ignore 
from typing import Any, Dict, List, Tuple
from urllib.parse import quote as url_encode

ROOT_URL = "http://psd.bits-pilani.ac.in"

def url(endpoint: str) -> str:
    return ROOT_URL + endpoint

def load_user_credentials() -> Tuple[str, str]:
    print("Loading user credentials... ", end="", flush=True)
    credentials_file = "credentials.txt"

    if not os.path.exists(credentials_file):
        print("Failure.\nCredentials file ({}) not found.".format(credentials_file))
        exit(1)
    
    data = []  # Sort of like a variable declaration
    with open(credentials_file, "r") as f:
        data = f.readlines()

    for i, line in enumerate(data, start=1):
        try:
            key, value = tuple(map(lambda x: x.strip(), line.split(":", maxsplit=1)))  # I'm sorry ':)
            if key == "username":
                txtemail = value
            elif key == "password":
                txtpass = value
            else:
                print("Failure.\n\"{}\" is an unrecognized key.".format(key))
                exit(1)
        except ValueError:
            # Skip lines which are purely whitespace.
            line = line.strip()
            if line != "":
                print("Failure.\nLine number {} in {} is invalid:\n{}".format(i, credentials_file, line))
                exit(1)

    if txtemail == "":
        print("Failure.\nUsername was not provided.")
        exit(1)
        
    if txtpass == "":
        print("Failure.\nPassword was not provided.")
        exit(1)

    print("Success.")
    return (txtemail, txtpass)

def authenticate(session: requests.Session, txtmail: str, txtpass: str) -> None:
    print("Logging in... ", end="", flush=True)
    login_url = url("/Login.aspx")

    # We need to fetch the login page with a GET request instead of directly posting because
    # this is an ASPX application and there are some specific POST parameters that we will
    # need to provide using the credentials from the fetched page. This is similar to needing
    # to GET before POSTing to extract a CSRF token for HTML forms.
    response = session.get(login_url)
    if response.status_code != 200:
        print("Failure.\nCould not fetch the login page.")
        exit(1)

    soup = BeautifulSoup(response.content, "html.parser")

    view_state = soup.find(id="__VIEWSTATE")["value"]
    view_state_generator = soup.find(id="__VIEWSTATEGENERATOR")["value"]
    event_validator= soup.find(id="__EVENTVALIDATION")["value"]

    # Now login using the user-supplied credentials and the page parameters.
    # The web application has this stupid design where if you specify incorrect credentials,
    # instead of getting a 401 you get a 200 and there is a little script tacked on to the
    # top of the HTML document saying that the provided credentials are correct.
    # But then again this application wasn't designed to be used as an API, so I guess I can't
    # blame them?
    # If you login with the right credentials then you will be redirected to the dashboard (302).
    form_data = {
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": view_state,
        "__VIEWSTATEGENERATOR": view_state_generator,
        "__EVENTVALIDATION": event_validator,
        "TxtEmail": txtemail,
        "txtPass": txtpass,
        "Button1": "Login",
        "txtEmailId": "",
    }
    response = session.post(login_url, data=form_data, allow_redirects=False)
    if response.status_code != 302:
        print("Failure.\nAre the credentials you provided correct?")
        exit(1)
    session.get(url(response.headers["Location"]))  # This redirect-triggered request will actually validate the session cookie. Which is weird...

    # Now we have a valid session cookie stored as "ASP.NET_SessionId".
    print("Success.")
    return

def load_stations(session: requests.Session) -> Dict[str, Any]:
    print("Loading the currently available stations... ", end="", flush=True)
    stations_data = {}  # type: Dict[str, Any]
    stations_data_endpoint = url("/Student/StudentStationPreference.aspx/getinfoStation")
    response = session.post(stations_data_endpoint, json={"CompanyId": "0"})  # We have to send a POST request to get data.... Ok, seriously, which IDIOT designed this portal?!
    if response.status_code != 200:
        print("Failed.")
        exit(1)
    stations_list = json.loads(response.json()["d"])
    for station in stations_list:
        stations_data[station["Companyname"].strip()] = {
            "sno": station["Sno"],
            "city": station["City"],
            "station_id": station["StationId"],
            "company_id": station["CompanyId"],
        }
    print("Success.")
    return stations_data

def load_user_station_preferences(stations_data: Dict[str, Any]) -> List[str]:
    """ This method will also validate the user station preferences. """
    print("Loading user station preferences... ", end="", flush=True)
    stations_file = "stations.txt"

    if not os.path.exists(stations_file):
        print("Failure.\nStations Preferences file ({}) not found.".format(stations_file))
        exit(1)
   
    user_station_preferences = []  # type: List[str]
    with open(stations_file, "r") as f:
        user_station_preferences = f.readlines()

    # Some lines might be a random mixture of whitespace so we can't
    # do verification short-circuiting by analyzing the length of
    # user_station_preferences.

    stations_seen = {}  # type: Dict[str, int]  # [name, line_number]
    validated_user_station_preferences = []
    for i, station in enumerate(user_station_preferences, start=1):
        station = station.strip()
        if station == "":
            continue  # This is how we filter out blank lines.
        if station not in stations_data:
            print("Failed.\nStation \"{}\" on line {} of {} is not a valid station.".format(station, i, stations_file))
            exit(1)
        if station in stations_seen:
            print("Failed.\nStation \"{}\" was originally on line {} of {} but was repeated on line {}.".format(station, stations_seen[station], stations_file, i))
            exit(1)
        stations_seen[station] = i
        validated_user_station_preferences.append(station)

    if len(validated_user_station_preferences) != len(stations_data):
        print("Failed.\nStations that you have to add to {}:\n{}".format(stations_file, set(stations_data) - set(validated_user_station_preferences)))
        exit(1)

    print("Success.")
    return validated_user_station_preferences

if __name__ == "__main__":
    session = requests.Session()
    txtemail, txtpass = load_user_credentials()
    authenticate(session, txtemail, txtpass)
    stations_data = load_stations(session)
    user_station_preferences = load_user_station_preferences(stations_data)
