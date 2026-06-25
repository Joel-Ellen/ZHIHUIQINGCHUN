import json

with open('job_profiles_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

profiles = data.get('profiles', {})
print(f'总岗位画像数: {len(profiles)}')

first_key = list(profiles.keys())[0]
print(f'第一条样例 ID={first_key}: {profiles[first_key]}')
print(f'维度: {data.get("dimensions", [])}')

# 生成 job_profiles.js
js_content = "const JOB_PROFILES = " + json.dumps(profiles, ensure_ascii=False, separators=(',', ':')) + ";\n"

with open('job_profiles.js', 'w', encoding='utf-8') as f:
    f.write(js_content)

print("已生成 job_profiles.js")
