"""Idempotent installer for bidirectional Argos Translate language packs via English pivot."""

from __future__ import annotations

import argparse
import sys
from typing import Iterable, List, Set, Tuple

PIVOT_LANG = "en"
DEFAULT_TARGET_LANGS: Tuple[str, ...] = ("pt", "es", "fr", "it", "de", "ru", "zh", "ja")


def build_required_pairs(
    target_langs: Iterable[str] = DEFAULT_TARGET_LANGS,
    pivot: str = PIVOT_LANG,
) -> List[Tuple[str, str]]:
    """Return ordered bidirectional (from_code, to_code) pairs pivoted through English."""
    pairs: List[Tuple[str, str]] = []
    seen: Set[Tuple[str, str]] = set()
    for code in target_langs:
        clean = (code or "").strip().lower()
        if not clean or clean == pivot:
            continue
        for pair in ((pivot, clean), (clean, pivot)):
            if pair not in seen:
                seen.add(pair)
                pairs.append(pair)
    return pairs


def ensure_argos_packages(
    target_langs: Iterable[str] = DEFAULT_TARGET_LANGS,
    pivot: str = PIVOT_LANG,
    dry_run: bool = False,
) -> Tuple[int, int, List[Tuple[str, str]]]:
    """Ensure all required bidirectional en<->lang packages are installed idempotently.

    Returns (already_installed_count, newly_installed_count, missing_from_index_pairs).
    """
    import argostranslate.package as argos_pkg

    desired_pairs = build_required_pairs(target_langs, pivot=pivot)
    installed = {(pkg.from_code, pkg.to_code) for pkg in argos_pkg.get_installed_packages()}
    missing = [pair for pair in desired_pairs if pair not in installed]
    already_count = len(desired_pairs) - len(missing)

    if not missing:
        print(f"Todos os {already_count} pacotes necessarios ja estao instalados.")
        return already_count, 0, []

    print(f"Pacotes ja instalados: {already_count}. Faltando: {len(missing)} -> {missing}")
    if dry_run:
        return already_count, 0, missing

    print("Atualizando indice de pacotes do Argos Translate...")
    argos_pkg.update_package_index()
    available = {(pkg.from_code, pkg.to_code): pkg for pkg in argos_pkg.get_available_packages()}

    installed_now = 0
    unavailable: List[Tuple[str, str]] = []
    for from_code, to_code in missing:
        pkg = available.get((from_code, to_code))
        if pkg is None:
            unavailable.append((from_code, to_code))
            print(f"[AVISO] Pacote {from_code}->{to_code} nao encontrado no indice.")
            continue
        print(f"Baixando e instalando {from_code}->{to_code}...")
        download_path = pkg.download()
        argos_pkg.install_from_path(download_path)
        installed_now += 1
        print(f"Instalado com sucesso: {from_code}->{to_code}")

    return already_count, installed_now, unavailable


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Instala modelos locais do Argos Translate usando ingles (en) como pivo."
    )
    parser.add_argument(
        "--langs",
        nargs="+",
        default=list(DEFAULT_TARGET_LANGS),
        help="Codigos ISO-639-1 dos idiomas alem do ingles (padrao: pt es fr it de ru zh ja).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lista apenas o que falta instalar sem baixar pacotes.",
    )
    args = parser.parse_args(argv)

    already_count, installed_now, missing = ensure_argos_packages(args.langs, dry_run=args.dry_run)
    print(
        f"Resumo: {already_count} ja presentes, {installed_now} instalados agora, "
        f"{len(missing)} pendentes/indisponiveis."
    )
    return 1 if (not args.dry_run and missing) else 0


if __name__ == "__main__":
    sys.exit(main())
