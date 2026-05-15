from src.storage.CacheManager import CacheManager

with CacheManager() as cache:
    print("COURSES:")
    for row in cache.get_all_courses():
        print(dict(row))

    print("\nDEPARTMENTS:")
    for row in cache.get_all_departments():
        print(dict(row))