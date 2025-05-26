with open("../logs/logging_2025-05-25-21-14.log", "r") as file:
    with open('../collected_commits/1000_stars_with_java_modification_and_perf_message.csv', 'w') as output_file:
        output_file.write("owner,repo,commit_hash,commit_url,commit_message\n")
        perf_mes = None
        repos = set()
        owners = set()
        for line in file:
            l = line.strip()
            if 'root INFO' in l:
                perf_mes = l.split('root INFO ')[1]
            elif 'https://' in l and "/commit/" in l:
                commit_hash = l.split('/')[-1].strip()
                owner = l.split('/')[-4].strip()
                repo = l.split('/')[-3].strip()
                perf_mes = perf_mes.replace(',', ' ')
                perf_mes = '- '.join(perf_mes.split('- ')[1:])
                if not('perf:' in perf_mes.lower() or 'performance' in perf_mes.lower()):
                    continue
                output_file.write(f"{owner},{repo},{commit_hash},{l},{perf_mes}\n")
                repos.add(f'{owner}/{repo}')
                owners.add(owner)
            else:
                perf_mes = perf_mes + " " + l
        print(f"Collected {len(repos)} repositories and {len(owners)} owners.")