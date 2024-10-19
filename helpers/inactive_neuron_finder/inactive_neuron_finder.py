from typing import Union
import os
import sys
from datetime import datetime
import pandas as pd


def get_todays_date() -> str:
    '''
    Gets today's date in the form: YYYY-MM-DD
    '''
    return datetime.today().strftime('%Y-%m-%d')


def get_file(file_path: str) -> Union[pd.DataFrame, None]:
    '''
    Checks if the file exists at the given path, and if it does, reads it into a DataFrame.
    '''
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    else:
        print(f"The file at {file_path} does not exist.")
        return None


def get_report() -> pd.DataFrame:
    '''
    Downloads the latest CSV report from the provided URL.
    Returns a DataFrame.
    '''
    # if file exists, read it
    predictors_report = get_file(f'predictors-{get_todays_date()}.csv')
    if predictors_report is None:
        # Read the CSV file directly from the URL
        predictors_report = pd.read_csv(
            'https://satorinet.io/reports/daily/predictors/latest')
        save(predictors_report, f'predictors-{get_todays_date()}.csv')
    lowest_report = get_file(f'lowest_performers-{get_todays_date()}.csv')
    if lowest_report is None:
        lowest_report = pd.read_csv(
            'https://satorinet.io/reports/daily/lowest/latest')
        save(lowest_report, f'lowest_performers-{get_todays_date()}.csv')
    # combine latest dfs into one, may contain duplicate values
    return pd.concat([predictors_report, lowest_report], ignore_index=True)


def get_list_of_addresses(csv_path: str) -> list:
    '''
    Gets a list of addresses from the first column of a CSV file.
    '''
    # Assuming the addresses are in the first column, ignore header
    return get_file(csv_path).iloc[1:, 0].tolist()


def find_missing_addresses(report: pd.DataFrame, addresses: list) -> pd.DataFrame:
    # Combine the two columns into a single set of unique values
    print(addresses)
    addresses_in_report = set(report['worker_address']).union(
        set(report['reward_address']))
    # Find the addresses in x that are not in the DataFrame
    missing_addresses = [
        addr for addr in addresses if addr not in addresses_in_report]
    print(missing_addresses)
    return pd.DataFrame(missing_addresses, columns=['missing addresses'])


def save(df: pd.DataFrame, path: str):
    '''
    Saves the DataFrame to a CSV file.
    '''
    df.to_csv(path, index=False)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python inactive_neuron_finder.py <addresses_csv_path> <missing_addresses_csv_save_path>")
    else:
        addresses_path = sys.argv[1]
        save_path = sys.argv[2]
        addresses = get_list_of_addresses(addresses_path)
        missing = find_missing_addresses(
            report=get_report(),
            addresses=addresses)
        save(
            path=save_path,
            df=missing)
        print(f'given addresses count: {len(addresses)}')
        print(f'Missing addresses count: {len(missing)}')
        print(f'Please see {save_path} for missing addresses')
