import sys
import time

if __name__ == "__main__":
    if len(sys.argv) > 1:
        station = sys.argv[1]
        print(f"Station {station} started.")
        time.sleep(1)
        print(f"Station {station} FINISHED_SUCCESSFULLY")
    else:
        print("No station provided.")
