#!/usr/bin/env python3
"""Run JobCompass GUI, collection CLI or deterministic CLI matching."""
import argparse
import json
import sys
from pathlib import Path
from jobcompass.config import DB_PATH
from jobcompass.server import Application, make_server
from jobcompass.sources import collect_api
from jobcompass.benchmark import import_snapshot
from jobcompass.jobsdb import collect as collect_jobsdb


def main():
    parser = argparse.ArgumentParser(description='JobCompass 智能求职平台')
    parser.add_argument('--port', type=int, default=8765, help='本机网页端口，默认 8765')
    parser.add_argument('--db', type=Path, default=DB_PATH, help='SQLite 数据库路径')
    parser.add_argument('--collect', choices=['JobsDB', 'Remotive', 'Arbeitnow'], help='采集岗位后退出')
    parser.add_argument('--limit', type=int, default=50, help='JobsDB 每次更新 1–200 条，默认 50')
    parser.add_argument('--keyword', default='', help='JobsDB 更新关键词，可留空')
    parser.add_argument('--demo', action='store_true', help='新数据库使用 12 条虚构样例；默认使用 JobsDB 历史研究数据')
    parser.add_argument('--import-benchmark', action='store_true', help='导入随附 JobsDB 研究快照后退出')
    parser.add_argument('--match', type=Path, help='用 TXT 简历执行 CLI 匹配后退出')
    parser.add_argument('--no-browser', action='store_true', help='不自动打开浏览器')
    parser.add_argument('--public', action='store_true', help='启用免登录访客隔离；需要配置 HTTPS 公开域名')
    parser.add_argument('--host', default='127.0.0.1', help='监听地址；非回环地址必须启用 --public')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('端口必须在 1 至 65535 之间。')
    if args.host not in ('127.0.0.1', 'localhost') and not args.public:
        parser.error('公开监听必须启用 --public，以隔离访客数据。')
    app = Application(args.db, demo=args.demo)
    try:
        if args.import_benchmark:
            print(json.dumps(import_snapshot(app.store), ensure_ascii=False, indent=2))
            return 0
        if args.collect:
            result = collect_jobsdb(app.store, args.limit, args.keyword) if args.collect == 'JobsDB' else collect_api(args.collect, app.store)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.match:
            app.post('/api/resume', {'text': args.match.read_text(encoding='utf-8')})
            for j in app.state()['jobs'][:10]:
                print('{:5.1f}  {} / {} / {}'.format(j['score'], j['title'], j['company'], j['source']))
            return 0
        if args.public:
            from jobcompass.public import PublicConfig
            public_config = PublicConfig.from_env()
        else:
            public_config = None
        server = make_server(app, args.port, host=args.host, public_config=public_config)
    except (OSError, ValueError) as exc:
        print('启动失败：{}'.format(exc), file=sys.stderr)
        app.tasks.pool.shutdown(wait=False)
        return 1
    url = public_config.origin if public_config else 'http://127.0.0.1:{}'.format(args.port)
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
