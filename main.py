#!/usr/bin/env python3
"""Run JobCompass GUI, collection CLI or deterministic CLI matching."""
import argparse
import json
import sys
from pathlib import Path
from jobcompass.config import DB_PATH
from jobcompass.server import Application, make_server
from jobcompass.sources import collect_api


def main():
    parser = argparse.ArgumentParser(description='JobCompass 智能求职平台')
    parser.add_argument('--port', type=int, default=8765, help='本机网页端口，默认 8765')
    parser.add_argument('--db', type=Path, default=DB_PATH, help='SQLite 数据库路径')
    parser.add_argument('--collect', choices=['Remotive', 'Arbeitnow'], help='采集公开岗位后退出')
    parser.add_argument('--match', type=Path, help='用 TXT 简历执行 CLI 匹配后退出')
    parser.add_argument('--no-browser', action='store_true', help='不自动打开浏览器')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('端口必须在 1 至 65535 之间。')
    app = Application(args.db)
    try:
        if args.collect:
            print(json.dumps(collect_api(args.collect, app.store), ensure_ascii=False, indent=2))
            return 0
        if args.match:
            app.post('/api/resume', {'text': args.match.read_text(encoding='utf-8')})
            for j in app.state()['jobs'][:10]:
                print('{:5.1f}  {} / {} / {}'.format(j['score'], j['title'], j['company'], j['source']))
            return 0
        server = make_server(app, args.port)
    except (OSError, ValueError) as exc:
        print('启动失败：{}'.format(exc), file=sys.stderr)
        app.tasks.pool.shutdown(wait=False)
        return 1
    url = 'http://127.0.0.1:{}'.format(args.port)
    print('JobCompass 已启动：{}\n按 Ctrl+C 停止。'.format(url), flush=True)
    if not args.no_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止服务。')
    finally:
        server.server_close()
        app.tasks.pool.shutdown(wait=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
