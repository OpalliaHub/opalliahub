"""File extraction and deterministic, evidence-based resume parsing."""
import io
import re
import zipfile
from xml.etree import ElementTree

SKILLS = {
    'Python': ['python'], 'SQL': ['sql', 'mysql', 'postgresql', 'sqlite'],
    'Java': ['java'], 'JavaScript': ['javascript', 'js'], 'TypeScript': ['typescript'],
    'React': ['react'], 'Vue': ['vue'], 'HTML/CSS': ['html', 'css'],
    'Pandas': ['pandas'], 'NumPy': ['numpy'], 'Excel': ['excel'],
    'Power BI': ['power bi', 'powerbi'], 'Tableau': ['tableau'],
    'Machine Learning': ['machine learning', '机器学习', 'scikit-learn', 'sklearn'],
    'PyTorch': ['pytorch'], 'TensorFlow': ['tensorflow'],
    'LLM': ['llm', '大模型', 'langchain', 'deepseek', 'rag'],
    'Flask': ['flask'], 'Django': ['django'], 'FastAPI': ['fastapi'],
    'Git': ['git', 'github'], 'Docker': ['docker'], 'Kubernetes': ['kubernetes', 'k8s'],
    'Linux': ['linux'], 'AWS': ['aws'], 'Azure': ['azure'],
    'Spark': ['spark'], 'Redis': ['redis'], 'MongoDB': ['mongodb'],
    'Testing': ['pytest', 'unittest', '测试', 'testing'],
    'Statistics': ['statistics', '统计'], 'Data Analysis': ['data analysis', '数据分析'],
    'Communication': ['communication', '沟通'], 'English': ['english', '英语', 'ielts'],
    'C++': ['c++'], 'Go': ['golang', 'go'], 'Figma': ['figma'],
}


def skills_in(text):
    lowered = text.lower()
    result = []
    for skill, aliases in SKILLS.items():
        for alias in aliases:
            pattern = re.escape(alias)
            if alias.isascii():
                pattern = r'(?<![a-z0-9_])' + pattern + r'(?![a-z0-9_])'
            if re.search(pattern, lowered):
                result.append(skill)
                break
    return result


def experience(text):
    values = re.findall(r'(\d+(?:\.\d+)?)\s*\+?\s*(?:年(?:以上)?(?:工作|相关|开发|实习)?经验|years?\s+(?:of\s+)?(?:professional\s+|work\s+|relevant\s+)?experience)', text, re.I)
    # Match the lower bound of ranges, not their upper bound.
    ranges = re.findall(r'(\d+)\s*[-–至]\s*\d+\s*(?:年|years?)', text, re.I)
    if ranges:
        return float(min(map(int, ranges)))
    if values:
        return min(50, max(map(float, values)))
    if re.search(r'应届|实习生|在读|fresh graduate|internship|entry.level', text, re.I):
        return 0.0
    return None


def education(text):
    for label, pattern in [('博士', r'博士|ph\.?d'), ('硕士', r'硕士|master'), ('本科', r'本科|学士|bachelor'), ('专科', r'专科|associate degree')]:
        if re.search(pattern, text, re.I):
            return label
    return '未识别'


def parse_resume(text):
    text = text.strip()
    if len(text) < 30:
        raise ValueError('简历至少需要 30 个字符，请补充教育、技能和项目经历。')
    if len(text) > 40000:
        raise ValueError('简历超过 40,000 字符，请精简后重试。')
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    skills = skills_in(text)
    evidence = {s: next((x[:220] for x in lines if s in skills_in(x)), '') for s in skills}
    return {'skills': skills, 'evidence': evidence, 'education': education(text),
            'experience_years': experience(text), 'characters': len(text),
            'strengths': ['简历中出现 {}：{}'.format(s, evidence[s]) for s in skills[:5]],
            'suggestions': ['用行动、方法、结果描述项目，并仅填写可核实的数字。',
                            '补充目标岗位相关成果、项目链接和可验证的技能证据。'], 'mode': 'local'}


def extract_file(filename, data):
    if len(data) > 5 * 1024 * 1024:
        raise ValueError('文件不能超过 5 MB。')
    suffix = filename.lower().rsplit('.', 1)[-1]
    try:
        if suffix in ('txt', 'md'):
            return data.decode('utf-8-sig')
        if suffix == 'docx':
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                info = archive.getinfo('word/document.xml')
                if info.file_size > 8 * 1024 * 1024:
                    raise ValueError('Word 文件解压内容过大。')
                tree = ElementTree.fromstring(archive.read(info))
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                return '\n'.join(''.join(t.text or '' for t in p.findall('.//w:t', ns)) for p in tree.findall('.//w:p', ns))
        if suffix == 'pdf':
            try:
                from pypdf import PdfReader
            except ImportError:
                raise ValueError('PDF 解析组件未安装。请运行 pip install -r requirements.txt，或粘贴简历文本。')
            reader = PdfReader(io.BytesIO(data))
            if len(reader.pages) > 30:
                raise ValueError('简历 PDF 不能超过 30 页。')
            text = '\n'.join(page.extract_text() or '' for page in reader.pages)
            if len(text.strip()) < 30:
                raise ValueError('此 PDF 没有足够的可提取文字，扫描件请先 OCR 或直接粘贴文本。')
            return text
    except ValueError:
        raise
    except Exception:
        raise ValueError('无法读取文件，请检查文件格式和编码，或直接粘贴文字。')
    raise ValueError('支持 TXT、MD、DOCX 和文字型 PDF 文件。')


def redact(text):
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[邮箱已隐藏]', text)
    text = re.sub(r'(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)', '[电话已隐藏]', text)
    return re.sub(r'(?<!\d)\d{17}[\dXx](?!\d)', '[证件号已隐藏]', text)
