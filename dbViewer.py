from src.storage.CacheManager import CacheManager

with CacheManager() as cache:
    print("COURSES:")
    for row in cache.get_all_courses():
        print(dict(row))

    print("\nDEPARTMENTS:")
    for row in cache.get_all_departments():
        print(dict(row))

    print("\nPREREQUISITES:")
    for row in cache.get_all_courses():
        prereqs = cache.get_prerequisites_for_course(row["course_id"])
        code = f"{row['department_code']}{row['course_number']}"
        if prereqs:
            prereq_codes = [f"{p['department_code']}{p['course_number']}" for p in prereqs]
            print(f"  {code}: {', '.join(prereq_codes)}")
        else:
            print(f"  {code}: (none)")