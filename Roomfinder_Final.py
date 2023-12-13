###
# IMPORT
###

import streamlit as st
import requests
import pandas as pd
from pandas import json_normalize
from datetime import datetime, time

###########################################################################
################################ Get Data #################################
###########################################################################


def get_room_dfs(StartDate_user, EndDate_user, building, floor_nr, seat_nr=None):

	############################################# Get all rooms #############################################
	#api
	url = "https://integration.preprod.unisg.ch/toolapi/Rooms"

	# Define headers for API request
	headers = {
		"X-ApplicationId": "587acf1c-24d0-4801-afda-c98f081c4678",
		"API-Version": "1",
		"X-RequestedLanguage": "en"
	}

	# Request Data from API
	response = requests.get(url, headers=headers)

	# Check for error in request
	if response.ok:

		# Transform json response to Pandas dataframe
		json_response = response.json()
		all_rooms = pd.DataFrame(json_response)

	#### Model DF all_rooms
		# Rename extracted columns for readability
		all_rooms.rename(columns={'floor': 'floor_nr'}, inplace=True)
		all_rooms.rename(columns={'seats': 'seat_nr'}, inplace=True)

		# Select only active rooms
		all_rooms = all_rooms[all_rooms['active'] == True]

		# Select only rooms that fit the filters
		if seat_nr is not None:
			all_rooms = all_rooms.query(f"seat_nr >= {seat_nr}")
		if building != "ALL":
			all_rooms = all_rooms.query(f"building == '{building}'")
		if floor_nr != "ALL":
			all_rooms = all_rooms.query(f"floor_nr == {int(floor_nr)}")

		# Drop unnecessary rooms
		rooms_to_exclude = ['Sporthalle', 'Dummy', '#OLMA', 'SQU', 'MLE', '#', "Covid"]
		for rooms in rooms_to_exclude:
			all_rooms = all_rooms[~all_rooms['shortName'].str.contains(rooms)]

		# Select only necessary columns
		selected_columns = ['id', 'shortName', 'building', 'floor_nr', 'seat_nr']
		all_rooms = all_rooms[selected_columns]

		# Define RoomId as Index
		all_rooms = all_rooms.set_index('id')
	else:
		print("Fehler beim Aufruf der API: ", response.status_code)

	###################################### Get yellow, orange and red rooms #######################################

	# API
	url = "https://integration.preprod.unisg.ch/eventapi/EventDates/byStartDate/{startDate}/byEndDate/{endDate}"

	# Replaces variables in API request with UserInput
	url = url.format(startDate=StartDate_user, endDate=EndDate_user)

	# Define headers for API request
	headers = {
		"X-ApplicationId": "587acf1c-24d0-4801-afda-c98f081c4678",
		"API-Version": "3",
		"X-RequestedLanguage": "en"
	}

	# Request Data from API
	response = requests.get(url, headers=headers)

	# Check for error in request
	if response.ok:

		# Transform json response to Pandas dataframe
		json_response = response.json()
		yellow_orange_red_rooms = pd.DataFrame(json_response)

	##### Model DF yellow_orange_red_rooms
		# Rename to ensure unique column names for Events before importing events from column room
		yellow_orange_red_rooms.rename(columns={'shortName': 'Event_shortName'}, inplace=True)
		yellow_orange_red_rooms.rename(columns={'id': 'Event_id'}, inplace=True)
		yellow_orange_red_rooms.rename(columns={'description': 'Event_description'}, inplace=True)

		# Extract room specifics (shortName, Building, Floor_nr...) from 'room' column
		# and add them as new columns to yellow_orange_red_rooms DF. Source: ChatGPT
		room_columns = json_normalize(yellow_orange_red_rooms['room'])
		yellow_orange_red_rooms = pd.concat([yellow_orange_red_rooms, room_columns], axis=1)

		# Rename extracted columns for readability
		yellow_orange_red_rooms.rename(columns={'floor': 'floor_nr'}, inplace=True)
		yellow_orange_red_rooms.rename(columns={'seats': 'seat_nr'}, inplace=True)

		# Select only rooms that fit the filters
		if seat_nr is not None:
			yellow_orange_red_rooms = yellow_orange_red_rooms.query(f"seat_nr >= {seat_nr}")
		if building != "ALL":
			yellow_orange_red_rooms = yellow_orange_red_rooms.query(f"building == '{building}'")
		if floor_nr != "ALL":
			yellow_orange_red_rooms = yellow_orange_red_rooms.query(f"floor_nr == {int(floor_nr)}")

		# Drop all unnecessary rooms
		for rooms in rooms_to_exclude:
			yellow_orange_red_rooms = yellow_orange_red_rooms[~yellow_orange_red_rooms['shortName'].str.contains(rooms)]

		# Select only necessary columns
		selected_columns = ['id', 'shortName', 'building', 'floor_nr', 'seat_nr', 'startTime', 'endTime']
		yellow_orange_red_rooms = yellow_orange_red_rooms[selected_columns]

		# Define RoomId as Index
		yellow_orange_red_rooms = yellow_orange_red_rooms.set_index('id')
	else:
		print("Fehler beim Aufruf der API: ", response.status_code)

	############################################# Get green rooms #############################################
	###### Create a boolean mask for rooms that are available. Source: ChatGPT
	# Checks if each id in all_rooms DF is not in the semi available or occupied rooms DF
	green_mask = ~all_rooms.index.isin(yellow_orange_red_rooms.index)

	# Apply the mask to get available rooms
	green_rooms = all_rooms[green_mask]

	############################################# Get yellow rooms #############################################
	###### Get rooms that are occupied at the user start time but get available during the duration
	yellow_rooms = yellow_orange_red_rooms[
		(yellow_orange_red_rooms['startTime'] <= StartDate_user) &
		(StartDate_user < yellow_orange_red_rooms['endTime']) &
		(yellow_orange_red_rooms['endTime'] < EndDate_user)
		]

	############################################# Get orange rooms #############################################
	###### Get rooms that are free at the user start time but not for the whole duration
	orange_rooms = yellow_orange_red_rooms[
		(StartDate_user < yellow_orange_red_rooms['startTime']) &
		(yellow_orange_red_rooms['startTime'] < EndDate_user) &
		(EndDate_user <= yellow_orange_red_rooms['endTime'])
		]

	############################################# Get red rooms #############################################
	###### Create a boolean masks for rooms that are semi available. Source: ChatGPT
	# Checks if each id in yellow_orange_rooms DF is not in the the yellow_rooms or orange_rooms DF
	red_mask1 = ~yellow_orange_red_rooms.index.isin(yellow_rooms.index)
	red_mask2 = ~yellow_orange_red_rooms.index.isin(orange_rooms.index)

	# Apply the mask to get occupied rooms
	red_rooms = yellow_orange_red_rooms[red_mask1]
	red_rooms = yellow_orange_red_rooms[red_mask2]

	# Return all desired room DFs
	return green_rooms, yellow_rooms, orange_rooms, red_rooms, all_rooms


###########################################################################
########################## FILTERS AND INTERFACE ##########################
###########################################################################

# Streamlit Title
st.title("Find your room at HSG")


############################## Select time period ##############################
# create a field to enter date
day = st.date_input("When do you want to book your room")

# create a slider to select timeslot
booking_time = st.slider(
	"Schedule your booking-time:",
	value=(time(12, 00), time(14, 00)))

# Extract the start and end time from the slider
start_time = booking_time[0]
end_time = booking_time[1]

# format the times to sth like 12:15:00
formatted_start_time = start_time.strftime("%H:%M:%S")
formatted_end_time = end_time.strftime("%H:%M:%S")

# convert times to datetime objects on the same arbitrary date
arbitrary_date = datetime(2000, 1, 1)
start_datetime = arbitrary_date.replace(hour=start_time.hour, minute=start_time.minute)
end_datetime = arbitrary_date.replace(hour=end_time.hour, minute=end_time.minute)
duration = (end_datetime - start_datetime).total_seconds() / 3600

# convert date type to string type: Source: ChatGPT
# create string to set date for the api
day_converted = str(day)
StartDate_user = day_converted + "T" + formatted_start_time
EndDate_user = day_converted + "T" + formatted_end_time


############################## Select building ##############################
# Create a random dataframe to get all building names
_, _, _, _,  building_df = get_room_dfs(StartDate_user="2023-12-20T12:15:00", EndDate_user="2023-12-20T14:00:00", building="ALL", floor_nr="0", seat_nr=0)

# Get unique values from the 'building' column
unique_buildings = building_df['building'].unique()

# Drop empty string and none values. Why do they exist????????
unique_buildings_list = [item for item in unique_buildings if item != "" or None]

# Sort list for UX
unique_buildings_list.sort()

# Add the option to select all buildings
unique_buildings_list = ["ALL"] + unique_buildings_list

# create a dropdown menu to select a building if wanted
building = st.selectbox("Select a building", unique_buildings_list)


############################## Select floor ##############################
floor_nr = st.selectbox("Select a floor", ["ALL", "-2", "-1", "0", "1", "2", "3", "4", "5", "6"])


############################## Select seats ##############################
seat_nr = st.slider("Select min seat number", 0, 50, 10)

# print what has been calculated and give feedback
st.write(f":arrow_right: You're looking for a room at {formatted_start_time[-8:-3]}h for {duration} hours")


###########################################################################
############################## Visualization ##############################
###########################################################################


# Implement error message to draw the attention of the user to the opening hours of HSG
try:

	# Do the Magic to get the DFs for the visualization ;)
	green_rooms, yellow_rooms, orange_rooms, red_rooms, _ = get_room_dfs(StartDate_user, EndDate_user, building, floor_nr, seat_nr)

#### Prepare DFs for displaying
	# Define a function to map the status to colors
	def status_to_color(status):
		if status == 'Green':
			return 'background-color: #00802f; color: #00802f;'
		elif status == 'Yellow':
			return 'background-color: #fef04a; color: #fef04a;'
		elif status == 'Orange':
			return 'background-color: #ff7f50; color: #ff7f50;'
		elif status == 'Red':
			return 'background-color: #eb6b69; color: #eb6b69;'

	# Add the 'Status' and 'Note' columns to green_rooms dataframe
	green_rooms['Status'] = 'Green'
	green_rooms['Note'] = 'This room is available.'

	# Add the 'Status' and 'Note' columns to yellow_rooms dataframe
	yellow_rooms['Status'] = 'Yellow'
	yellow_rooms['Note'] = (
		'This room is occupied but becomes available at: '
		+ yellow_rooms['endTime'].astype(str).str[-8:-3] + 'h.'
	)

	# Add the 'Status' and 'Note' columns to orange_rooms dataframe
	orange_rooms['Status'] = 'Orange'
	orange_rooms['Note'] = (
		'This room is free at the beginning but will be occupied starting from: '
		+ orange_rooms['startTime'].astype(str).str[-8:-3] + 'h.'
	)

	# Add the 'Status' and 'Note' columns to red_rooms dataframe
	red_rooms['Status'] = 'Red'
	red_rooms['Note'] = 'This room is occupied.'

	# Customize column widths individually
	column_widths = {
		'Status': 50,
		'Room': 200,
		'Note': 350,
		'Seats': 50
	}

	# Fix double index entries: Some rooms host multiple events in the time frame requested -> two entries in DF -> keep only first one
	yellow_rooms = yellow_rooms.loc[~yellow_rooms.index.duplicated(keep='first')]
	orange_rooms = orange_rooms.loc[~orange_rooms.index.duplicated(keep='first')]
	red_rooms = red_rooms.loc[~red_rooms.index.duplicated(keep='first')]

#### Display DF
	# Display the green rooms with 'Status', 'Room', 'Note', and 'Seats' columns
	# Apply the style and table sizes defined above; Source: ChatGPT (.applymap and .set_table_styles basic framework)
	st.write("<h3>Green Rooms (Available)</h3>", unsafe_allow_html=True)
	# Sent a message instead of displaying the DF in case DF is empty
	if green_rooms.empty:
		st.write("No Green Rooms available", unsafe_allow_html=True)
	else:
		st.table(green_rooms.rename(columns={'shortName': 'Room', 'seat_nr': 'Seats'})[['Status', 'Room', 'Note', 'Seats']].style.applymap(status_to_color, subset=['Status']).set_table_styles([{'selector': f'.col{i}', 'props': [('width', f'{column_widths.get(col, 150)}px')] } for i, col in enumerate(['Status', 'Room', 'Note', 'Seats'])]))

	# Display the green rooms with 'Status', 'Room', 'Note', and 'Seats' columns
	# Apply the style and table sizes defined above; Source: ChatGPT (.applymap and .set_table_styles basic framework)
	st.write("<h3>Yellow Rooms (Occupied but become available)</h3>", unsafe_allow_html=True)
	# Sent a message instead of displaying the DF in case DF is empty
	if yellow_rooms.empty:
		st.write("No Yellow Rooms available", unsafe_allow_html=True)
	else:
		st.table(yellow_rooms.rename(columns={'shortName': 'Room', 'seat_nr': 'Seats'})[['Status', 'Room', 'Note', 'Seats']].style.applymap(status_to_color, subset=['Status']).set_table_styles([{'selector': f'.col{i}', 'props': [('width', f'{column_widths.get(col, 150)}px')] } for i, col in enumerate(['Status', 'Room', 'Note', 'Seats'])]))

	# Display the green rooms with 'Status', 'Room', 'Note', and 'Seats' columns
	# Apply the style and table sizes defined above; Source: ChatGPT (.applymap and .set_table_styles basic framework)
	st.write("<h3>Orange Rooms (Free at start but not for the whole duration)</h3>", unsafe_allow_html=True)
	# Sent a message instead of displaying the DF in case DF is empty
	if orange_rooms.empty:
		st.write("No Orange Rooms available", unsafe_allow_html=True)
	else:
		st.table(orange_rooms.rename(columns={'shortName': 'Room', 'seat_nr': 'Seats'})[['Status', 'Room', 'Note', 'Seats']].style.applymap(status_to_color, subset=['Status']).set_table_styles([{'selector': f'.col{i}', 'props': [('width', f'{column_widths.get(col, 150)}px')] } for i, col in enumerate(['Status', 'Room', 'Note', 'Seats'])]))

	# Display the green rooms with 'Status', 'Room', 'Note', and 'Seats' columns
	# Apply the style and table sizes defined above; Source: ChatGPT (.applymap and .set_table_styles basic framework)
	st.write("<h3>Red Rooms (Occupied)</h3>", unsafe_allow_html=True)
	# Sent a message instead of displaying the DF in case DF is empty
	if red_rooms.empty:
		st.write("No Red Rooms available", unsafe_allow_html=True)
	else:
		st.table(red_rooms.rename(columns={'shortName': 'Room','seat_nr': 'Seats'})[['Status', 'Room', 'Note', 'Seats']].style.applymap(status_to_color, subset=['Status']).set_table_styles([{'selector': f'.col{i}', 'props': [('width', f'{column_widths.get(col, 150)}px')] } for i, col in enumerate(['Status', 'Room', 'Note', 'Seats'])]))

# Implement error message to draw the attention of the user to the opening hours of HSG
except KeyError:
	error_message = "&#10060; Something went wrong! &#10060;"
	note = "Did you choose a timeframe that lies within the opening hours of HSG?"

	st.markdown(
		f'<div style="font-size: 18px; font-weight: bold; text-align: center;">{error_message}</div>',
		unsafe_allow_html=True
	)
	st.markdown(
		f'<div style="font-size: 18px; font-weight: bold; text-align: center;">{note}</div>',
		unsafe_allow_html=True
	)
