import base64, requests, sys, os
from io import BytesIO
from pathlib import Path

KEY_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../mykey.py'))

def _prepare_image(image_input, max_pixels=1440000):
    """加载+缩放+base64编码，返回b64字符串"""
    from PIL import Image
    if isinstance(image_input, Image.Image):
        img = image_input
    elif isinstance(image_input, (str, Path)):
        img = Image.open(image_input)
    else:
        raise TypeError(f"image_input 必须是文件路径或PIL Image，实际: {type(image_input).__name__}")
    w, h = img.size
    if w * h > max_pixels:
        scale = (max_pixels / (w * h)) ** 0.5
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        print(f"  📐 缩放: {w}×{h} → {new_w}×{new_h}")
    if img.mode in ('RGBA', 'LA', 'P'):
        rgb = Image.new('RGB', img.size, (255, 255, 255))
        rgb.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = rgb
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=80, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    print(f"  📦 Base64: {len(buf.getvalue())/1024:.1f}KB")
    return b64

def _load_config():
    key_dir = os.path.dirname(KEY_PATH)
    if key_dir not in sys.path: sys.path.append(key_dir)
    import mykey
    return mykey

def _call_claude(b64, prompt, timeout, max_tokens=1024):
    mk = _load_config()
    cfg = mk.claude_config141
    resp = requests.post(
        cfg['apibase'] + '/v1/messages',
        json={'model': cfg['model'], 'max_tokens': max_tokens, 'messages': [{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64}},
                {'type': 'text', 'text': prompt}
            ]
        }]},
        headers={'x-api-key': cfg['apikey'], 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
        timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()['content'][0]['text']

def _call_openai(b64, prompt, timeout):
    mk = _load_config()
    cfg = mk.oai_config1
    proxies = {'https': cfg['proxy'], 'http': cfg['proxy']} if cfg.get('proxy') else None
    resp = requests.post(
        cfg['apibase'] + '/chat/completions',
        json={'model': cfg['model'], 'messages': [{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': prompt},
                {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64}'}}
            ]
        }]},
        headers={'Authorization': f"Bearer {cfg['apikey']}", 'Content-Type': 'application/json'},
        proxies=proxies, timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content']

def ask_vision(image_input, prompt="详细描述这张图片的内容", timeout=60, max_pixels=1440000, backend='claude'):
    """
    Vision API（默认Claude，可选openai）
    :param backend: 'claude'(默认) 或 'openai'
    """
    try:
        b64 = _prepare_image(image_input, max_pixels)
    except Exception as e:
        return f"Error: 图片处理失败 - {type(e).__name__}: {e}"
    try:
        if backend == 'claude': return _call_claude(b64, prompt, timeout)
        elif backend == 'openai': return _call_openai(b64, prompt, timeout)
        else: return f"Error: 未知backend '{backend}'，可选: claude, openai"
    except requests.exceptions.Timeout:
        return f"Error: 请求超时 (>{timeout}s)"
    except requests.exceptions.RequestException as e:
        return f"Error: API请求失败 - {type(e).__name__}: {e}"
    except (KeyError, ValueError) as e:
        return f"Error: 响应解析失败 - {e}"

if __name__ == '__main__':
    print('✅ Vision API 已就绪 (默认Claude后端, 支持openai切换)')