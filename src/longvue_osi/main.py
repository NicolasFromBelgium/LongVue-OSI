# src/longvue_osi/main.py
import argparse
from .database import initialize_database


def main():
    parser = argparse.ArgumentParser(description="LongVue-OSI OSINT Scraping Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Commande pour init DB
    subparsers.add_parser("init_db", help="Initialize the database")

    # Commande pour scrape
    scrape_parser = subparsers.add_parser(
        "scrape", help="Run the OSINT scraper"
    )  # Keep if you add args below
    scrape_parser.add_argument(
        "--url", type=str, default="https://example.com", help="Starting URL for scraping"
    )

    args = parser.parse_args()

    if args.command == "init_db":
        initialize_database()
        print("Database initialized successfully.")
    elif args.command == "scrape":
        from .scraper import run_scraper  # Lazy import

        run_scraper(start_url=args.url)
        print("Scraping completed.")


if __name__ == "__main__":
    main()
