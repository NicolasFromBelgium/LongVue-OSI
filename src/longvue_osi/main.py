# src/tdd_template/main.py
from .database import initialize_database  # Changed to relative import

def main():
    initialize_database()

if __name__ == "__main__":
    main()
