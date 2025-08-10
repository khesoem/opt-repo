def get_found_performance_commits(log_file_path):
    repos = set()
    owners = set()
    to_write = set()
    with open(log_file_path, "r") as file:
        perf_mes = None
        for line in file:
            l = line.strip()
            if 'root INFO' in l:
                perf_mes = l.split('root INFO ')[1]
            elif 'https://' in l and "/commit/" in l:
                l = l.split('Found performance commit: ')[-1]
                commit_hash = l.split('/')[-1].strip()
                owner = l.split('/')[-4].strip()
                repo = l.split('/')[-3].strip()
                perf_mes = perf_mes.replace(',', ' ')
                perf_mes = '- '.join(perf_mes.split('- ')[1:])
                to_write.add(f"{owner},{repo},{commit_hash},{l},{perf_mes}\n")
                repos.add(f'{owner}/{repo}')
                owners.add(owner)
            else:
                perf_mes = perf_mes + " " + l
    return repos, owners, to_write

with open('collected_commits/1000_stars_maven_repos_with_perf_message.csv', 'w') as output_file:
    repos1, owners1, to_write1 = get_found_performance_commits("logs/logging_2025-08-06-13-22.log")
    repos, owners, to_write = get_found_performance_commits("logs/logging_2025-08-04-20-44.log")
    repos = repos.union(repos1)
    owners = owners.union(owners1)
    to_write = to_write.union(to_write1)

    output_file.write("owner,repo,commit_hash,commit_url,performance_message\n")
    for line in to_write:
        output_file.write(line)

    print(f"Collected {len(repos)} repositories and {len(owners)} owners.")