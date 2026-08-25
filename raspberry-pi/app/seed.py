from .hospital_data import init_hospital_db, seed_demo_data


def main() -> None:
    init_hospital_db()
    counts = seed_demo_data()
    print("CareGrid hackathon demo seed complete")
    for table, count in counts.items():
        print(f"{table}: {count}")


if __name__ == "__main__":
    main()
