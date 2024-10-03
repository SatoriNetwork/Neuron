import requests
import json

class SatoriServer:
    def __init__(self, base_url):
        self.base_url = base_url

    def getTestData(self):
        """
        Fetch test data from the SatoriCentral server.
        """
        try:
            url = f"{self.base_url}/api/test"
            print(f"Requesting URL: {url}")
            response = requests.get(url)
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.text}")
            if response.status_code == 200:
                return response.json()
            else:
                return {"status": "error", "message": f"HTTP {response.status_code}", "content": response.text}
        except requests.RequestException as e:
            print(f"Error occurred while fetching test data: {str(e)}")
            return {"status": "error", "message": str(e)}



def main():
    # Initialize the server with the SatoriCentral URL
    server = SatoriServer("http://satoricentral:5000")
    
    # Fetch test data
    result = server.getTestData()
    
    # Print the result
    print("Test Data Result:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()