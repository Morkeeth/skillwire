from pathlib import Path
import os
import subprocess

root=Path(__file__).parent
env={k:v for k,v in os.environ.items() if k not in ('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL','CLAUDE_CODE_OAUTH_TOKEN','OPENAI_API_KEY')}
env['DISABLE_TELEMETRY']='1'
claude=Path.home()/'.local/bin/claude'
for arm in ('plain','guided'):
    work=root/arm
    args=[str(claude),'-p','--model','opus','--effort','medium','--no-session-persistence','--setting-sources','','--mcp-config',str(root/'mcp.json'),'--strict-mcp-config','--tools','']
    with (work/'input.txt').open() as prompt, (work/'out.txt').open('w') as out, (work/'err.log').open('w') as err:
        try:
            done=subprocess.run(args, stdin=prompt,stdout=out,stderr=err,env=env,cwd=work,timeout=125)
            status=done.returncode
        except subprocess.TimeoutExpired:
            status=124
    (work/'exit').write_text(str(status)+'\n')
    print(f'{arm}: {status}',flush=True)
    if status:
        break
