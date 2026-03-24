import json
import os
import requests
import re
import difflib
import datetime

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from typing import Any, Text, Dict, List


API_BASE = "http://localhost:5001/api"


# -----------------------------
# Load stations dataset
# -----------------------------
current_dir = os.path.dirname(__file__)

stations_file = os.path.join(current_dir, "stations.json")

if not os.path.exists(stations_file):
    stations_file = os.path.join(current_dir,  "stations.json")

with open(stations_file, "r", encoding="utf-8") as f:
    stations = json.load(f)


# -----------------------------
# Build lookup tables
# -----------------------------
station_by_code = {}
station_by_name = {}

for station in stations:

    code = station["stationCode"].lower()
    name = station["stationName"].lower()

    station_by_code[code] = station["stationCode"]
    station_by_name[name] = station["stationCode"]


# -----------------------------
# Station aliases
# -----------------------------
city_alias = {

    "trivandrum": "tvc",
    "tvm": "tvc",
    "thiruvananthapuram": "tvc",

    "calicut": "clt",
    "kozhikode": "clt",

    "cochin": "ern",
    "kochi": "ern",
    "ernakulam": "ern",

    "thrissur": "tcr",
    "trichur": "tcr",

    "alleppey": "allp",
    "alappuzha": "allp",

    "palghat": "pgtn",
    "palakkad": "pgtn"
}


# -----------------------------
# Detect requested day
# -----------------------------
def detect_day(text):

    text = text.lower()

    days = {
        "monday": "Mon",
        "tuesday": "Tue",
        "wednesday": "Wed",
        "thursday": "Thu",
        "friday": "Fri",
        "saturday": "Sat",
        "sunday": "Sun",

        "mon": "Mon",
        "tue": "Tue",
        "wed": "Wed",
        "thu": "Thu",
        "fri": "Fri",
        "sat": "Sat",
        "sun": "Sun"
    }

    for d in days:
        if d in text:
            return days[d]

    if "today" in text:
        return datetime.datetime.today().strftime("%a")

    if "tomorrow" in text:
        return (datetime.datetime.today() + datetime.timedelta(days=1)).strftime("%a")

    return None


# -----------------------------
# Detect date
# -----------------------------
def detect_date(text):

    text = text.lower()

    match = re.search(r'(\d{1,2})[/-](\d{1,2})([/-](\d{2,4}))?', text)

    if match:

        day = int(match.group(1))
        month = int(match.group(2))

        if match.group(4):
            year = int(match.group(4))
        else:
            year = datetime.datetime.today().year

        try:
            date_obj = datetime.datetime(year, month, day)
            return date_obj.strftime("%a")
        except:
            return None

    months = {
        "january":1,"february":2,"march":3,"april":4,
        "may":5,"june":6,"july":7,"august":8,
        "september":9,"october":10,"november":11,"december":12
    }

    words = text.split()

    for i, word in enumerate(words):

        if word.isdigit():

            d = int(word)

            if i + 1 < len(words):

                m = words[i + 1]

                if m in months:

                    try:
                        date_obj = datetime.datetime(
                            datetime.datetime.today().year,
                            months[m],
                            d
                        )
                        return date_obj.strftime("%a")
                    except:
                        return None

    return None


# -----------------------------
# Find station code
# -----------------------------
def find_station_code(query):

    if not query:
        return None

    query = query.lower().strip()

    if query in city_alias:
        alias_code = city_alias[query]
        if alias_code in station_by_code:
            return station_by_code[alias_code]

    if query in station_by_code:
        return station_by_code[query]

    if query in station_by_name:
        return station_by_name[query]

    for name, code in station_by_name.items():
        if query in name:
            return code

    matches = difflib.get_close_matches(
        query,
        station_by_name.keys(),
        n=1,
        cutoff=0.5
    )

    if matches:
        return station_by_name[matches[0]]

    return None


# -----------------------------
# Extract stations from message
# -----------------------------
def extract_stations(text):

    text = text.lower()

    text = re.sub(r'[^\w\s]', ' ', text)

    words = text.split()

    ignore_words = {
        "train", "trains", "from", "to",
        "today", "tomorrow",
        "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday",
        "mon", "tue", "wed", "thu", "fri", "sat", "sun"
    }

    station_candidates = []

    for word in words:

        if word in ignore_words:
            continue

        code = find_station_code(word)

        if code and code not in station_candidates:
            station_candidates.append(code)

    if len(station_candidates) >= 2:
        return station_candidates[0], station_candidates[1]

    return None, None


# -----------------------------
# Train Search Action
# -----------------------------
class ActionSearchTrain(Action):

    def name(self) -> Text:
        return "action_search_train"

    def run(self, dispatcher, tracker, domain):

        user_text = tracker.latest_message.get("text")

        is_next_train = "next" in user_text.lower()

        source_code, dest_code = extract_stations(user_text)

        day = detect_day(user_text)

        if not day:
            day = detect_date(user_text)

        if not source_code or not dest_code:
            dispatcher.utter_message(
                text="I couldn't detect both stations. Try something like 'clt to tvc'."
            )
            return []

        try:

            url = f"{API_BASE}/trains/between-stations?source={source_code}&destination={dest_code}"

            response = requests.get(url)

            if response.status_code != 200:
                dispatcher.utter_message(
                    text="Failed to fetch train data."
                )
                return []

            trains = response.json()

            if not trains:
                dispatcher.utter_message(
                    text=f"No trains found from {source_code} to {dest_code}."
                )
                return []

            filtered_trains = []

            for train in trains:

                from_station = train.get("fromStation", {})
                to_station = train.get("toStation", {})

                if (
                    from_station.get("isHalt") and
                    to_station.get("isHalt") and
                    from_station.get("departureTime")
                ):
                    filtered_trains.append(train)

            trains = filtered_trains

            if day:
                trains = [
                    t for t in trains
                    if day in t.get("runningDays", [])
                ]

            if not trains:
                dispatcher.utter_message(
                    text=f"No trains halt between {source_code} and {dest_code}."
                )
                return []

            def time_to_minutes(t):
                try:
                    h, m = map(int, t.split(":"))
                    return h * 60 + m
                except:
                    return 9999

            if is_next_train:

                now = datetime.datetime.now()
                current_minutes = now.hour * 60 + now.minute

                future_trains = []

                for train in trains:

                    dep = train.get("fromStation", {}).get("departureTime")

                    if dep:
                        dep_minutes = time_to_minutes(dep)

                        if dep_minutes >= current_minutes:
                            future_trains.append(train)

                trains = future_trains

            trains.sort(
                key=lambda x: time_to_minutes(
                    x.get("fromStation", {}).get("departureTime", "23:59")
                )
            )

            if is_next_train:
                trains = trains[:1]
                message = f"Next train from {source_code} to {dest_code}:\n\n"
            else:
                trains = trains[:8]
                message = f"Trains from {source_code} to {dest_code}:\n\n"

            for train in trains:

                departure = train.get("fromStation", {}).get("departureTime", "N/A")
                arrival = train.get("toStation", {}).get("arrivalTime", "N/A")

                runs = train.get("runningDays", [])

                if isinstance(runs, list):
                    days_text = " ".join(runs)
                else:
                    days_text = str(runs)

                message += (
                    f"{train.get('trainName')} ({train.get('trainNumber')})\n"
                    f"Departure: {departure}\n"
                    f"Arrival: {arrival}\n"
                    f"Runs On: {days_text}\n\n"
                )

            dispatcher.utter_message(text=message)

        except requests.exceptions.ConnectionError:
            dispatcher.utter_message(
                text="Unable to connect to SmartRail server."
            )

        except Exception as e:
            dispatcher.utter_message(
                text=f"Unexpected error: {str(e)}"
            )

        return []


# -----------------------------
# Seat Recommendation Action
# -----------------------------
class ActionSeatRecommendation(Action):

    def name(self) -> Text:
        return "action_seat_recommendation"

    def run(self, dispatcher, tracker, domain):

        passenger_type = next(tracker.get_latest_entity_values("type"), None)

        # Support typed text also
        if not passenger_type:

            user_text = tracker.latest_message.get("text").lower()

            if "elderly" in user_text or "senior" in user_text or "old" in user_text:
                passenger_type = "elderly"

            elif "pregnant" in user_text:
                passenger_type = "pregnant"

            elif "child" in user_text or "kid" in user_text or "baby" in user_text:
                passenger_type = "child"

            elif "general" in user_text or "adult" in user_text:
                passenger_type = "general"

        # Seat suggestions
        if passenger_type == "elderly":

            message = (
                "If you're travelling with an elderly passenger, a lower berth "
                "is usually the best option since it’s easier to access and "
                "avoids climbing during the journey."
            )

        elif passenger_type == "pregnant":

            message = (
                "For pregnant passengers, a lower berth is generally the "
                "safest and most comfortable option."
            )

        elif passenger_type == "child":

            message = (
                "When travelling with children, a lower berth or side lower berth "
                "is usually a good choice so parents can keep an eye on them easily."
            )

        elif passenger_type == "general":

            message = (
                "Most passengers prefer a lower berth for convenience, "
                "while upper berths are better if you want fewer disturbances "
                "during overnight travel."
            )

        else:

            buttons = [
                {"title": "Elderly passenger", "payload": '/seat_recommendation{"type":"elderly"}'},
                {"title": "Pregnant passenger", "payload": '/seat_recommendation{"type":"pregnant"}'},
                {"title": "Travelling with children", "payload": '/seat_recommendation{"type":"child"}'},
                {"title": "General passenger", "payload": '/seat_recommendation{"type":"general"}'}
            ]

            dispatcher.utter_message(
                text="Tell me your travel needs so I can recommend the best berth .",
                buttons=buttons
            )

            return []

        # Send the seat suggestion
        dispatcher.utter_message(text=message)

        # Show main menu again
        dispatcher.utter_message(response="utter_main_menu")

        return []

class ActionAskTrainNumber(Action):

    def name(self):
        return "action_ask_train_number"

    def run(self, dispatcher, tracker, domain):

        dispatcher.utter_message(
            text="Please type the train number (for example: 12801)."
        )

        return []


class ActionAskWLNumber(Action):

    def name(self):
        return "action_ask_wl_number"

    def run(self, dispatcher, tracker, domain):

        dispatcher.utter_message(
            text="What is your waiting list number? (Example: WL12 or 12)"
        )

        return []


import re
from rasa_sdk import Action
from rasa_sdk.events import SlotSet


class ActionPredictWL(Action):

    def name(self):
        return "action_predict_wl"

    def run(self, dispatcher, tracker, domain):

        train_number = tracker.get_slot("train_number")
        coach = tracker.get_slot("coach")

        # Ensure train number exists
        if not train_number:
            dispatcher.utter_message(
                text="Please enter a valid train number first."
            )
            return []

        # Ensure coach/class selected
        if not coach:
            dispatcher.utter_message(
                text="Please select the coach/class first."
            )
            return []

        user_text = tracker.latest_message.get("text", "")

        match = re.search(r"\d+", user_text)

        if not match:
            dispatcher.utter_message(
                text="Please enter a valid waiting list number (example: WL12)."
            )
            return []

        wl = int(match.group())

        dispatcher.utter_message(
            text=f"Your ticket status is WL{wl}."
        )

        # Prediction logic
        if coach == "SL":
            if wl <= 5:
                prediction = "Very high chance of confirmation."
            elif wl <= 20:
                prediction = "High chance of confirmation."
            elif wl <= 40:
                prediction = "Moderate chance of confirmation."
            else:
                prediction = "Very unlikely to confirm."

        elif coach == "3A":
            if wl <= 3:
                prediction = "Very high chance of confirmation."
            elif wl <= 15:
                prediction = "Moderate chance of confirmation."
            else:
                prediction = "Low chance of confirmation."

        elif coach == "2A":
            if wl <= 2:
                prediction = "Very high chance of confirmation."
            elif wl <= 10:
                prediction = "Moderate chance of confirmation."
            else:
                prediction = "Low chance of confirmation."

        elif coach == "CC":
            if wl <= 10:
                prediction = "High chance of confirmation."
            else:
                prediction = "Low chance of confirmation."

        elif coach == "2S":
            if wl <= 15:
                prediction = "Moderate chance of confirmation."
            else:
                prediction = "Low chance of confirmation."

        else:
            prediction = "Prediction unavailable for this class."

        dispatcher.utter_message(
            text=f"Prediction: {prediction}"
        )

        dispatcher.utter_message(
            response="utter_main_menu"
        )

        return [SlotSet("wl_number", wl)]

class ActionValidateTrainNumber(Action):

    def name(self):
        return "action_validate_train_number"

    def run(self, dispatcher, tracker, domain):

        user_text = tracker.latest_message.get("text", "")

        match = re.search(r"\b\d{5}\b", user_text)

        if not match:
            dispatcher.utter_message(
                text="Please enter a valid 5-digit train number (example: 12801)."
            )
            return []

        train_number = match.group()

        try:

            url = f"{API_BASE}/trains/{train_number}"
            response = requests.get(url)

            # Train not found
            if response.status_code != 200:

                dispatcher.utter_message(
                    text=f"{train_number} doesn't appear to be a valid train number."
                )

                return [
                    SlotSet("train_number", None),
                    SlotSet("coach", None)
                ]

            train = response.json()

            if not train:

                dispatcher.utter_message(
                    text=f"{train_number} doesn't appear to be a valid train number."
                )

                return [
                    SlotSet("train_number", None),
                    SlotSet("coach", None)
                ]

            train_name = train.get("trainName")

            if train_name:
                dispatcher.utter_message(
                    text=f"{train_name} ({train_number}) detected."
                )
            else:
                dispatcher.utter_message(
                    text=f"Train number {train_number} detected."
                )

            dispatcher.utter_message(
                text="Which class are you travelling in?",
                buttons=[
                    {"title": "SL", "payload": '/coach_select{"coach":"SL"}'},
                    {"title": "3A", "payload": '/coach_select{"coach":"3A"}'},
                    {"title": "2A", "payload": '/coach_select{"coach":"2A"}'},
                    {"title": "CC", "payload": '/coach_select{"coach":"CC"}'},
                    {"title": "2S", "payload": '/coach_select{"coach":"2S"}'}
                ]
            )

            return [SlotSet("train_number", train_number)]

        except Exception:

            dispatcher.utter_message(
                text="Unable to verify train number right now."
            )

            return [
                SlotSet("train_number", None),
                SlotSet("coach", None)
            ]

class ActionAskWLNumber(Action):

    def name(self):
        return "action_ask_wl_number"

    def run(self, dispatcher, tracker, domain):

        coach = tracker.get_slot("coach")

        if coach:
            dispatcher.utter_message(
                text=f"You selected {coach}. What is your waiting list number? (Example: WL12)"
            )
        else:
            dispatcher.utter_message(
                text="Please select the class first."
            )

        return []