"""
人脸一致性图片生成服务

- 有 GPU (CUDA): 本地 Stable Diffusion + IP-Adapter FaceID → 保持人脸一致
- 无 GPU: 返回 None → 调用方降级到 GLM-Image + 文本描述
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_pipeline = None
_pipeline_available: bool | None = None  # None=未检测, True/False=已检测

REF_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "ref"
DEFAULT_REF = REF_DIR / "junyi.jpg"


def _find_reference_image() -> Path | None:
    """查找参考照片"""
    if DEFAULT_REF.exists():
        return DEFAULT_REF
    if REF_DIR.exists():
        for f in REF_DIR.glob("*.jpg"):
            return f
        for f in REF_DIR.glob("*.png"):
            return f
    return None


def is_available() -> bool:
    """检测本地 SD + IP-Adapter 是否可用（不导入 torch，避免 GPU 初始化在主进程崩溃）。
    所有 GPU 实际检测在子进程中完成。"""
    global _pipeline_available

    if _pipeline_available is not None:
        return _pipeline_available

    # 仅检查模型缓存，不碰 CUDA
    try:
        from huggingface_hub import try_to_load_from_cache
        sd_config = try_to_load_from_cache("runwayml/stable-diffusion-v1-5", "model_index.json")
        if sd_config:
            _pipeline_available = True
            return True
        _pipeline_available = False
        return False
    except Exception:
        _pipeline_available = False
        return False


def _load_pipeline():
    """懒加载 SD + IP-Adapter 管线（首次调用时加载，节省内存）"""
    global _pipeline

    if _pipeline is not None:
        return _pipeline

    if not is_available():
        return None

    try:
        import torch
        from diffusers import StableDiffusionPipeline

        logger.info("Loading Stable Diffusion + IP-Adapter pipeline...")

        pipe = StableDiffusionPipeline.from_pretrained(
            "runwayml/stable-diffusion-v1-5",
            torch_dtype=torch.float16,
            safety_checker=None,
        ).to("cuda")

        # 加载 IP-Adapter FaceID（人脸一致性）
        pipe.load_ip_adapter(
            "h94/IP-Adapter",
            subfolder="models",
            weight_name="ip-adapter-plus-face_sd15.safetensors",
        )

        # 启用内存优化
        pipe.enable_attention_slicing()

        _pipeline = pipe
        logger.info("SD + IP-Adapter pipeline loaded successfully")
        return pipe

    except ImportError as e:
        logger.warning(f"diffusers not installed: {e}")
        _pipeline_available = False
        return None
    except Exception as e:
        logger.error(f"Failed to load SD pipeline: {e}")
        _pipeline_available = False
        return None


def generate_with_face(
    prompt: str,
    reference_image: str | Path | None = None,
    num_steps: int = 25,
    guidance_scale: float = 7.5,
    ip_adapter_scale: float = 0.75,
    width: int = 512,
    height: int = 512,
    negative_prompt: str = "",
) -> str | None:
    """
    使用参考照片生成人脸一致的图片。

    Args:
        prompt: 中文绘图提示词
        reference_image: 参考人脸照片路径（默认查找 static/ref/junyi.jpg）
        num_steps: 推理步数
        ip_adapter_scale: 人脸一致性强度 (0-1)，越高越像原图

    Returns:
        生成的图片文件路径，失败或无 GPU 返回 None
    """
    pipe = _load_pipeline()
    if pipe is None:
        return None

    # 查找参考照片
    ref_path = Path(reference_image) if reference_image else _find_reference_image()
    if not ref_path or not ref_path.exists():
        logger.warning(f"Reference image not found: {ref_path}")
        return None

    try:
        from diffusers.utils import load_image
        import torch

        ref_img = load_image(str(ref_path))

        # 默认负向提示词
        if not negative_prompt:
            negative_prompt = (
                "nsfw, lowres, bad anatomy, bad hands, text, error, missing fingers, "
                "extra digit, fewer digits, cropped, worst quality, low quality, "
                "normal quality, jpeg artifacts, signature, watermark, username, blurry"
            )

        logger.info(f"Generating img2img with reference: prompt={prompt[:60]}...")
        result = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image=ref_img,           # img2img: 基于参考照片改造
            strength=0.55,            # 保留约45%原始结构（服装/姿势/道具）
            ip_adapter_image=ref_img, # IP-Adapter: 保持人脸相似
            ip_adapter_scale=ip_adapter_scale,
            num_inference_steps=num_steps,
            guidance_scale=guidance_scale,
        ).images[0]

        # 保存图片
        output_dir = REF_DIR.parent / "generated"
        output_dir.mkdir(parents=True, exist_ok=True)

        import time
        filename = f"face_gen_{int(time.time())}.png"
        output_path = output_dir / filename
        result.save(str(output_path))

        # 返回可访问的 URL 路径
        return f"/static/generated/{filename}"

    except Exception as e:
        logger.error(f"Face-consistent generation failed: {e}")
        return None


def generate_cover_with_face(
    topic: str,
    article_content: str,
    reference_image: str | Path | None = None,
) -> str | None:
    """
    生成带人脸一致性的文章封面图。

    流程: 主题+文章片段 → DeepSeek 写绘图 prompt → SD+IP-Adapter 出图
    降级: GPU 不可用时返回 None → 调用方用 GLM-Image
    """
    if not is_available():
        return None

    from .article_generator import generate_image_prompt

    # 复用现有的 prompt 生成逻辑
    img_prompt = generate_image_prompt(topic, article_content)
    if not img_prompt:
        return None

    # 补充中文质量提示词
    img_prompt = (
        f"{img_prompt}, masterpiece, best quality, highly detailed, "
        f"cute boy, warm lighting, 3D render, Pixar style, vibrant colors"
    )

    return generate_with_face(prompt=img_prompt, reference_image=reference_image)


def _generate_in_subprocess(
    prompt: str,
    reference_image: str,
    num_steps: int = 20,
    guidance_scale: float = 7.0,
    ip_adapter_scale: float = 1.0,
    width: int = 512,
    height: int = 512,
) -> str | None:
    """在子进程中执行 GPU 生成，避免 SD 管线 segfault 影响主服务。"""
    import subprocess, tempfile, sys

    out_dir = Path(__file__).resolve().parent.parent.parent / "static" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"avatar_{int(__import__('time').time())}.png"

    script = f'''
import os, sys
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
sys.path.insert(0, r"{Path(__file__).resolve().parent.parent.parent}")
from app.services.face_image_generator import _load_pipeline, generate_with_face
pipe = _load_pipeline()
if pipe is None:
    print("PIPELINE_FAILED")
    sys.exit(1)
result = generate_with_face(
    prompt=r"""{prompt}""",
    reference_image=r"{reference_image}",
    num_steps={num_steps},
    guidance_scale={guidance_scale},
    ip_adapter_scale={ip_adapter_scale},
    width={width},
    height={height},
)
if result:
    import shutil
    shutil.copy(result, r"{out_path}")
    print("OK:" + r"{out_path}")
else:
    print("GENERATION_FAILED")
'''

    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=180,
        )
        output = proc.stdout.strip()
        if output.startswith("OK:") and out_path.exists():
            return "/static/generated/" + out_path.name
        logger.warning(f"Subprocess GPU generation failed: {output[:200]}")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("Subprocess GPU generation timed out")
        return None
    except Exception as e:
        logger.warning(f"Subprocess GPU generation error: {e}")
        return None


def generate_avatar(reference_image: str | Path | None = None, use_gpu: bool = False) -> str | None:
    """生成儿子的专属卡通头像。

    Args:
        reference_image: 参考照片路径
        use_gpu: True=尝试GPU(img2img)再降级GLM, False=直接GLM-Image（默认）
    Returns:
        图片 URL 路径，失败返回 None
    """
    ref_path = Path(reference_image) if reference_image else _find_reference_image()
    if not ref_path or not ref_path.exists():
        logger.warning(f"Reference image not found for avatar: {ref_path}")
        return None

    avatar_prompt = (
        "a cute Chinese cowboy boy, full body shot, small figure centered in frame, "
        "wearing western cowboy hat and vest, standing in a prairie with cacti, "
        "warm sunset lighting, highly detailed, 3D render, C4D, Pixar style"
    )

    # Step 1: 尝试本地 SD（仅在 use_gpu=True 时）
    if use_gpu and is_available():
        result = _generate_in_subprocess(
            prompt=avatar_prompt,
            reference_image=str(ref_path),
            num_steps=20,
            guidance_scale=7.0,
            ip_adapter_scale=1.0,
            width=512,
            height=512,
        )
        if result:
            return result

    # Step 2: 降级 GLM-Image
    try:
        from ..config import GLM_API_KEY, GLM_IMAGE_MODEL
        import httpx

        if not GLM_API_KEY:
            return None

        # 用参考照片文件名提示长相
        child_hint = ""
        if CHILD_APPEARANCE:
            child_hint = f"，外貌特征：{CHILD_APPEARANCE}"

        glm_prompt = (
            f"卡通头像，一个7岁中国小男孩，头戴鸭舌帽，身穿西部牛仔装，"
            f"腰间挎着左轮手枪，双手叉腰，一脸自信的笑容，"
            f"皮克斯风格，3D渲染，柔和光影，纯色背景{child_hint}"
        )

        resp = httpx.post(
            "https://open.bigmodel.cn/api/paas/v4/images/generations",
            headers={
                "Authorization": f"Bearer {GLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": GLM_IMAGE_MODEL, "prompt": glm_prompt},
            timeout=60.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            urls = data.get("data", [])
            if urls:
                url = urls[0].get("url")
                if url:
                    logger.info(f"Avatar generated via GLM-Image: {url}")
                    # Download and save locally to avoid long URL overflow in DB
                    try:
                        img_resp = httpx.get(url, timeout=30.0)
                        if img_resp.status_code == 200:
                            output_dir = REF_DIR.parent / "generated"
                            output_dir.mkdir(parents=True, exist_ok=True)
                            import time
                            filename = f"avatar_{int(time.time())}.png"
                            output_path = output_dir / filename
                            output_path.write_bytes(img_resp.content)
                            local_url = f"/static/generated/{filename}"
                            logger.info(f"Avatar saved locally: {local_url}")
                            return local_url
                    except Exception as e:
                        logger.warning(f"Failed to download GLM avatar: {e}")
                    return url  # fallback to remote URL if download fails
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"GLM-Image avatar fallback failed: {e}")

    return None


# 需要在文件末尾导入（避免循环引用）
from ..config import CHILD_APPEARANCE
