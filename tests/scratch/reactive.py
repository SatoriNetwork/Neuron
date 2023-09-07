from rx import Observable, Observer

source = Observable.from_list([1,2,3,4,5,6])

source.subscribe(lambda value: print("Received {0}".format(value)))

class PrintObserver(Observer):

    def on_next(self, value):
        print("Received {0}".format(value))

    def on_completed(self):
        print("Done!")

    def on_error(self, error):
        print("Error Occurred: {0}".format(error))

    def on_close(self):
        self.combine_latest_sbs.dispose()
        print("WebSocket closed")
    
source.subscribe(PrintObserver())