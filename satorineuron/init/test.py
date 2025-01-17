import asyncio
from start import StartupDag
from satorilib.concepts.structs import Stream, StreamId


async def test_initialize_data_client():
    # Create an instance of StartupDag
    startup = StartupDag()
    # Create test streams
    # test_streams = [
    #     Stream(
    #         streamId=StreamId(
    #             source="test_source_1",
    #             author="test_author_1",
    #             stream="test_stream_1",
    #             target="test_target_1"
    #         )
    #     ),
    #     Stream(
    #         streamId=StreamId(
    #             source="test_source_2",
    #             author="test_author_2",
    #             stream="test_stream_2",
    #             target="test_target_2"
    #         )
    #     )
    # ]
    
    # Set up test subscriptions and publications
    # startup.subscriptions = test_streams
    # startup.publications = test_streams[1:] 
    
    print("Starting DataClient initialization...")
    
    # Call the function we want to test
    await startup.initializeDataClient()
    
    print("DataClient initialization completed")
    
    if startup.dataClient is not None:
        print("✓ DataClient was successfully initialized")
    else:
        print("✗ DataClient initialization failed")

# Run the test
if __name__ == "__main__":
    print("Testing initializeDataClient function...")
    asyncio.run(test_initialize_data_client())
    print("Test completed")