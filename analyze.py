from collections import defaultdict
from difflib import SequenceMatcher
from datetime import date, datetime, timedelta
from dateutil.relativedelta import *
from copy import deepcopy
import csv
import json


# Basic gyst is that this will accept a bunch of charges
# From there it will organize and group these charges by title
# Once these charges are grouped it will try to determine if the charge is recuring and if so, what the cadience of the recuring charge is
### It does this by creating potential charge 'paths' then determining which one is the most 'best'
### This is a really rough description :/

def run_main_collector(transactions):

	def _similar_title(a, b):
		if a[:5].lower() == b[:5].lower(): 
			return 1.0
		return SequenceMatcher(None, a, b).ratio()

	def get_charge_groups(list_of_all_charges, match_val=.8):
		# Groups all charges together by how simular their title is (.8 is a total guestimate)
		grouped_charges_dict = defaultdict(list)
		for charge in list_of_all_charges:
			found_group = False
			for grouped_charge_title in grouped_charges_dict:
				if _similar_title(charge.title, grouped_charge_title) > match_val:
					found_group = True
					grouped_charges_dict[grouped_charge_title].append(charge)
					break
			if not found_group:
				grouped_charges_dict[charge.title] = [charge]
		grouped_charges = []
		for _, list_of_grouped_charges in grouped_charges_dict.items():
			grouped_charges.append(charge_group(list_of_grouped_charges))
		return grouped_charges

	def _get_paths_with_time_jump(charge_group, path_time_jump): # TODO redo
		# Collects all paths with a given time jump, (charge_group pre-sorted by time)
		# For each charge jump forward the given amount of time collecting charges that occur on that date,
		# till you reach the end of the charge list or hit the current day
		
		all_paths_with_time_jump = []
		# The charges are organized by time, make each charge could be the start the path
		for charge_pos, charge in enumerate(charge_group.charge_list):
			cur_path = [[charge]]
			next_date = charge.date + relativedelta(**path_time_jump) # TODO: include a range prob off by 1 (this would help if ex. no charge on a holiday)
			while charge_pos < len(charge_group.charge_list):
				cur_charge = charge_group.charge_list[charge_pos]
				charges_in_date_range = []
				while cur_charge.date <= next_date:
					if cur_charge.date == next_date: # TODO here is where I would check the range
						# found a charge that takes place on the next(current) day in the path
						charges_in_date_range.append(cur_charge)
					charge_pos = charge_pos + 1
					if charge_pos > len(charge_group.charge_list) - 1:
						break
					cur_charge = charge_group.charge_list[charge_pos]

				cur_path.append(charges_in_date_range)
				next_date = next_date + relativedelta(**path_time_jump)
			all_paths_with_time_jump.append(path(cur_path, path_time_jump))
		return all_paths_with_time_jump

	def get_all_paths(charge_group):
		# Gets all paths for a given charge group
		all_paths = []

		paths_to_concider = []
		# for days_to_jump in range(1, 32):
		# 	paths_to_concider.append({"days": days_to_jump})
		for weeks_to_jump in range(1, 5):
			paths_to_concider.append({"weeks": weeks_to_jump})
		for months_to_jump in range(1, 13):
			paths_to_concider.append({"months": months_to_jump})

		for path_time_jump in paths_to_concider:
			all_paths.extend(_get_paths_with_time_jump(charge_group, path_time_jump))
		return all_paths

	class charge_group():
		def __init__(self, grouped_charge_list):
			self.charge_list = grouped_charge_list

		def _disambiguate_path(self, path):
			# If there are two charges on the same day, pick the charge closest in price to the og charge
			# This prob isn't the best way to do this, w/ discounts on first charge and everything, will prob want to pick the charge closest to the mean
			first_charge_cost = path[0][0].cost
			new_path = []
			for p in path:
				if len(p) > 1:
					best_p = []
					best_p_score = 1000000000
					for cur_p in p:
						if abs(cur_p.cost - first_charge_cost) < best_p_score:
							best_p = [cur_p]
							best_p_score = cur_p.cost - first_charge_cost
					new_path.append(best_p)
				else:
					new_path.append(p)
			return new_path

		def _break_path(sef, path, max_break=3):
			cur_break = 0
			new_path = []
			for p in path:
				new_path.append(p)
				if not p:
					cur_break = cur_break + 1
				else:
					cur_break = 0
				if cur_break >= max_break:
					break
			while new_path and new_path[-1] == []:
				new_path = new_path[:-1]
			return new_path

		def _get_prices(self, charge_list):
			prices = []
			for x in charge_list:
				if x:
					prices.append(x[0].cost)
			return prices

		def _get_price_score(self, path):
			prices  = self._get_prices(path.charge_list)
			mode_price = max(set(prices), key = prices.count)
			average_price = sum(prices)/float(len(prices))
			return mode_price, average_price, prices.count(mode_price) / float(len(prices)), prices

		def _get_hit_ratio(self, path):
			return (float(len(path.charge_list))-path.charge_list.count([]))/float(len(path.charge_list))

		def get_best_path_1(self, charge_group_all_paths, hit_ratio_threshold=.75):
			path_stats = []
			for path in charge_group_all_paths:
				new_path = deepcopy(path)
				# These 2 calls should prob be in the path class but w/e
				new_path.charge_list = self._disambiguate_path(new_path.charge_list)
				new_path.charge_list = self._break_path(new_path.charge_list)
				mode_price, average_price, mode_price_ratio, prices = self._get_price_score(new_path)
				mode_price_ratio = 1 if mode_price_ratio > .5 else 0
				hit_ratio_score = 1 if self._get_hit_ratio(new_path) >= hit_ratio_threshold else 0
				# This huristic seams to work well, but its in no way fullproof
				path_stats.append((hit_ratio_score, mode_price_ratio, len(prices), new_path))
			path_stats.sort()
			return path_stats[-1]

	class path():
		def __init__(self, charge_list, jump):
			self.charge_list = charge_list
			self.jump = jump

	class charge():
		def __init__(self, title, date, cost):
			self.date = date
			self.title = title
			self.cost = cost

	# Transactions taken from plaid
	# List of charges ordered by time
	list_of_charges = []
	for x in json.loads(transactions.response[0])['transactions']['transactions']:
		list_of_charges.insert(0, charge(x['name'], datetime.strptime(x['date'], "%Y-%m-%d"), x['amount']))
	# List of charges grouped by title and ordered by time
	charge_groups = get_charge_groups(list_of_charges)

	return_charges = []
	for charge_group in charge_groups:
		# For each group of charges collect all possible paths for them
		charge_group_all_paths = get_all_paths(charge_group)
		# Finally use a huristic to find the most likely path or none if none of them pass a threshold
		best_path = charge_group.get_best_path_1(charge_group_all_paths)

		PERFECT_PRICE_THRESHOLD = 3
		if best_path:
			bad_prices = False
			# If the length of the list is less than 3 (chosen arbitrary), the prices must match perfectly
			if len(best_path[-1].charge_list) <= PERFECT_PRICE_THRESHOLD:
				og_charge_price = best_path[-1].charge_list[0][0].cost
				for charge in best_path[-1].charge_list:
					if charge[0].cost != og_charge_price:
						bad_prices = True
						break
			if bad_prices:
				continue
			# If theres only one datapoint obv reject
			# Make 2 one with 4 for stricter (no resturants)
			if len(best_path[-1].charge_list) < 2:
				continue

			print relativedelta(**best_path[-1].jump)
			cur_return_charges = ""
			for charge in best_path[-1].charge_list:
				if charge:
					print charge[0].title, charge[0].date, charge[0].cost
					# cur_return_charges.append({"title": str(charge[0].title), "date": str(charge[0].date.date()), "cost": "$" + str(charge[0].cost)})
					cur_return_charges += str(charge[0].title) + " " + str(charge[0].date.date()) + " " + str(charge[0].cost) + "<br>"
				else:
					cur_return_charges += "MISS - NO CHARGE THIS WEEK/MONTH" + "<br>"
					print "MISS - NO CHARGE THIS WEEK/MONTH"
			weeks_or_months = str(best_path[-1].jump["months"]) + " month(s)" if "months" in best_path[-1].jump else str(best_path[-1].jump["weeks"]) + " weeks(s)"
			return_charge_description = "Looks like you have a recuring charge to " + str(charge[0].title) + " for $" + str(charge[0].cost) + " repeating every " + weeks_or_months + ". The next charge should occur on " + str((charge[0].date + relativedelta(**best_path[-1].jump)).date())
			return_charges.append({"charges": cur_return_charges, "description": return_charge_description})
			print charge[0].title, charge[0].date + relativedelta(**best_path[-1].jump), charge[0].cost
			print "\n\n\n"
			print return_charges[-1]



	print "\n\n\n"
	print "\n\n\n"
	print "\n\n\n"
	print "\n\n\n"
	print "\n\n\n"
	return return_charges



# ususally they're charge backs or cancelation fees, but hey they might be something else

# from plaid import Client

# Available environments are 'sandbox', 'development', and 'production'.
# client = Client(client_id='5e7596887ba2dd00148a4423', secret='860cceb22f462e323de9492ff5e16b', public_key='eb9037d40f4e90ac8667487d6ac5ac', environment='sandbox')
# response = client.Item.public_token.exchange(public_token)
# access_token = response['access_token']
