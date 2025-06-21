#!/usr/bin/env python3
import argparse
import asyncio
import logging
import sys
import os
import subprocess
import shutil
import json
from functools import partial
from typing import Any

import faster_whisper
from wyoming.info import AsrModel, AsrProgram, Attribution, Info
from wyoming.server import AsyncServer

from . import __version__
from .wfw.handler import FasterWhisperEventHandler

_LOGGER = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        required=True,
        help="Name of faster-whisper model to use",
    )
    parser.add_argument(
        "--uri",
        required=True,
        help="unix:// or tcp://",
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        action="append",
        help="Data directory to check for downloaded models",
    )
    parser.add_argument(
        "--model-dir",
        required=True,
        help="Directory to download/load whisper models",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda", "auto"],
        help="Device to use for inference (default: cpu, cuda, auto)",
    )
    parser.add_argument(
        "--cpu-threads",
        type=int,
        default=0,
        help="Number of CPU threads to use for inference in case of CPU device (default: 0, which means all available threads)",
    )
    parser.add_argument(
        "--language",
        help="Default language to set for transcription",
    )
    parser.add_argument(
        "--compute-type",
        default="default",
        help="Compute type (default, auto, int8, int_float32, int8_float16, int8_bfloat16, int16, float16, float32, bfloat16)",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=5,
        help="Size of beam during decoding",
    )
    parser.add_argument(
        "--initial-prompt",
        help="Optional text to provide as a prompt for the first window",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Don't check HuggingFace hub for updates every time",
    )
    parser.add_argument(
        "--model-type",
        default="ct2",
        choices=["ct2", "distil", "transformers", "convert"],
        help="model type to use (ct2[faster-whisper], distil, transformers, convert[convert transformers model to CTranslate2 format]). default: ct2",
    )
    #
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Log DEBUG messages",
    )
    parser.add_argument(
        "--log-format",
        default=logging.BASIC_FORMAT,
        help="Format for log messages",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
        help="Print version and exit",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO, format=args.log_format
    )
    _LOGGER.debug(
        "args:\n%s", json.dumps(vars(args), indent=4, sort_keys=True)
    )

    # Resolve model name
    model_name = args.model

    if args.language == "auto":
        # Whisper does not understand "auto"
        args.language = None

    hf_token = None
    if os.getenv("HUGGINGFACE_HUB_TOKEN"):
        hf_token = os.getenv("HUGGINGFACE_HUB_TOKEN")
    elif os.getenv("HF_TOKEN"):
        hf_token = os.getenv("HF_TOKEN")


    wyoming_info = Info(
        asr=[
            AsrProgram(
                name="whispywiser",
                description="Custom Faster Whisper transcription with CTranslate2",
                attribution=Attribution(
                    name="Guillaume Klein",
                    url="https://github.com/guillaumekln/faster-whisper/",
                ),
                installed=True,
                version=__version__,
                models=[
                    AsrModel(
                        name=model_name,
                        description=model_name,
                        attribution=Attribution(
                            name="Systran",
                            url="https://huggingface.co/Systran",
                        ),
                        installed=True,
                        languages=faster_whisper.tokenizer._LANGUAGE_CODES,  # pylint: disable=protected-access
                        version=faster_whisper.__version__,
                    )
                ],
            )
        ],
    )

    _LOGGER.debug(
        "wyoming_info:\n%s", json.dumps(vars(wyoming_info), indent=4, sort_keys=True)
    )

    # Load model
    _LOGGER.debug("Loading %s", args.model)
    whisper_model: Any = None
    model_type = args.model_type.lower() or "ct2"
    if model_type == "convert":
        # Convert model
        try:
            converter_path = shutil.which("ct2-transformers-converter")
            if converter_path is None:
                raise FileNotFoundError("ct2-transformers-converter not found in PATH.")
            logging.info(f"Found converter at: {converter_path}")

            model_path = os.path.join(args.model_dir, model_name)
            model_conversion_path = os.path.join(args.model_dir, model_name + "-converted")
            DONE_FLAG = os.path.join(model_conversion_path, ".done")

            if os.path.exists(DONE_FLAG):
                print("Model already converted. Skipping conversion.")
                converted = True
                model_name = model_name + "-converted"
                subprocess_task_converted = True

            if not converted:
                if "int8" not in args.compute_type:
                    quantization = "int8"
                else:
                    quantization = "float16"

                result = subprocess.run([
                    "ct2-transformers-converter",
                    "--model", model_path,
                    "--output_dir", model_conversion_path,
                    "--quantization", quantization,
                    "--copy_files", "tokenizer.json", "preprocessor_config.json"
                ], check=True, capture_output=True, text=True)
                logging.info("Conversion successful:\n%s", result.stdout)
                open(DONE_FLAG, "w").close()
                model_name = model_name + "-converted"
                subprocess_task_converted = True

        except subprocess.CalledProcessError as e:
            logging.error("Conversion failed:\n%s", e.stderr)
            sys.exit("Conversion process failed. Check logs.")
        except FileNotFoundError as e:
            logging.error(f"{e}")
            sys.exit("Exiting: Required tool not found.")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            sys.exit("Exiting: Unexpected error.")

    if model_type == "transformers":
        # Use HuggingFace transformers
        from .wfw.transformers_whisper import TransformersWhisperModel

        whisper_model = TransformersWhisperModel(
            args.model, args.model_dir, args.local_files_only
        )
    elif model_type == "ct2" or model_type == "distil" or subprocess_task_converted:
        # Use faster-whisper
        whisper_model = faster_whisper.WhisperModel(
            args.model,
            download_root=args.model_dir,
            device=args.device.lower(),
            compute_type=args.compute_type,
            cpu_threads=args.cpu_threads,
            local_files_only=args.local_files_only,
            use_auth_token=hf_token,
        )

    server = AsyncServer.from_uri(args.uri)
    _LOGGER.info("Ready")
    model_lock = asyncio.Lock()

    if model_type == "transformers":
        # Use HuggingFace transformers
        from .wfw.transformers_whisper import (
            TransformersWhisperEventHandler,
            TransformersWhisperModel,
        )

        assert isinstance(whisper_model, TransformersWhisperModel)

        # TODO: initial prompt
        await server.run(
            partial(
                TransformersWhisperEventHandler,
                wyoming_info,
                args.language,
                args.beam_size,
                whisper_model,
                model_lock,
            )
        )
    elif model_type == "ct2" or model_type == "distil" or subprocess_task_converted:
        # Use faster-whisper
        assert isinstance(whisper_model, faster_whisper.WhisperModel)
        await server.run(
            partial(
                FasterWhisperEventHandler,
                wyoming_info,
                args,
                whisper_model,
                model_lock,
                initial_prompt=args.initial_prompt,
            )
        )


# -----------------------------------------------------------------------------


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass
