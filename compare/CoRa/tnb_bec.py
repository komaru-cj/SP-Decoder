"""Pure-Python port of the TnB block error correction (BEC) decoder.

CoRa's paper does not stop at symbol classification: Section III explicitly
feeds the classified symbols to TnB's BEC decoder.  The upstream CoRa artifact
shells out to MATLAB for that stage.  MATLAB is not available on the receiver,
so this module ports the same algorithm at the deinterleaved codeword-matrix
level:

* robust CR4 explicit-header block correction and header CRC closure;
* the CR1/CR2/CR3/CR4 column-error candidate rules from ``zlecc_decode_blk``;
* Cartesian candidate schedules with TnB's per-CR CRC-attempt caps; and
* payload CRC closure after standard LoRa dewhitening.

The original MATLAB files at commit ``bb33e98`` are vendored under
``upstream/TnB_bb33e98`` for a line-by-line audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product

import numpy as np

from lora_phy_decode import gray_inverse_map
from usrp_b210_lora_tx import (
    WHITENING_SEQ,
    hamming_encode,
    int_to_bits,
    lora_payload_crc,
)


HEADER_CHECKSUM_MATRIX = np.asarray(
    [
        [1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 1],
        [0, 1, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0],
        [0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 1, 1],
        [0, 0, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1],
    ],
    dtype=np.uint8,
)[::-1]


@dataclass(frozen=True)
class TnBBECResult:
    payload: bytes
    phy_crc_ok: bool
    header_nibbles: list[int]
    coding_rate: int
    payload_length: int
    crc_enabled: bool
    made_crc_attempts: int
    total_candidate_schedules: int
    additionally_corrected_codewords: int
    status: str


def _bits_to_int(bits: np.ndarray | list[int]) -> int:
    # LoRa's systematic Hamming columns are [d3,d2,d1,d0], while the
    # corresponding nibble is d0*8+d1*4+d2*2+d3.  This is MATLAB bi2de's
    # default right-msb convention used by the exact TnB source.
    return sum(int(bit) << index for index, bit in enumerate(bits))


def _codebook(cr: int) -> np.ndarray:
    width = 4 + int(cr)
    return np.asarray(
        [int_to_bits(hamming_encode(nibble, int(cr)), width) for nibble in range(16)],
        dtype=np.uint8,
    )


def _nearest_codewords(received: np.ndarray, cr: int) -> np.ndarray:
    h = _codebook(cr)
    active = 4 + int(cr)
    distance = np.sum(
        np.abs(received[:, None, :active].astype(np.int16) - h[None, :, :]),
        axis=2,
    )
    return h[np.argmin(distance, axis=1)]


def _deinterleave_matrix(
    symbols: list[int] | np.ndarray,
    *,
    sf: int,
    sf_app: int,
    codeword_width: int,
) -> np.ndarray:
    """Inverse of the transmitter interleaver, preserving symbol columns."""

    if len(symbols) != codeword_width:
        raise ValueError("symbol block length must equal codeword width")
    rows = np.asarray([int_to_bits(int(value), sf) for value in symbols], dtype=np.uint8)
    matrix = np.zeros((sf_app, codeword_width), dtype=np.uint8)
    for symbol_index, row in enumerate(rows):
        for codeword_index in range(sf_app):
            source = (symbol_index - codeword_index - 1) % sf_app
            matrix[source, symbol_index] = row[codeword_index]
    return matrix


def _check_selection(
    codebook: np.ndarray,
    selected_columns: list[int] | np.ndarray,
    received: np.ndarray,
) -> tuple[bool, np.ndarray]:
    selected = np.asarray(selected_columns, dtype=np.int64)
    keep = np.ones(received.shape[1], dtype=bool)
    keep[selected] = False
    corrected = received.copy()
    for row_index, row in enumerate(received):
        matches = np.flatnonzero(np.all(codebook[:, keep] == row[None, keep], axis=1))
        if matches.size == 0:
            return False, received.copy()
        corrected[row_index] = codebook[int(matches[0])]
    return True, corrected


def _difference_structure(
    corrected: np.ndarray,
    received: np.ndarray,
    known_bad_columns: list[int] | np.ndarray = (),
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    difference = corrected.astype(np.int16) - received.astype(np.int16)
    ranks = np.sum(np.abs(difference), axis=1)
    diff0 = np.flatnonzero(ranks == 0)
    diff1 = np.flatnonzero(ranks == 1)
    diff2 = np.flatnonzero(ranks == 2)
    locations = set(int(value) for value in known_bad_columns)
    for row_index in diff1:
        locations.update(int(value) for value in np.flatnonzero(difference[row_index]))
    return diff0, diff1, diff2, np.asarray(sorted(locations), dtype=np.int64)


@dataclass(frozen=True)
class _Common:
    cr2_group: np.ndarray
    cr3_group: np.ndarray
    cr4_group: np.ndarray
    cr4_two_group: np.ndarray


def _generate_common(codebook8: np.ndarray) -> _Common:
    """Port of ``zlecc_gen_common`` for this codebook's column ordering."""

    groups: dict[int, list[list[int]]] = {2: [], 3: [], 4: []}
    for cr, choose_count in ((2, 1), (3, 2), (4, 3)):
        width = 4 + cr
        raw: list[list[int]] = []
        for chosen in combinations(range(width), choose_count):
            flag = np.zeros(width, dtype=np.uint8)
            flag[list(chosen)] = 1
            derived = None
            for row in codebook8[:, :width]:
                diff = flag.astype(np.int16) - row.astype(np.int16)
                changed = np.flatnonzero(diff)
                if changed.size == 1:
                    derived = int(changed[0])
            if derived is not None:
                raw.append([*chosen, derived])
        if cr == 4:
            unique: list[list[int]] = []
            seen: set[tuple[int, ...]] = set()
            for row in raw:
                key = tuple(sorted(row))
                if key not in seen:
                    seen.add(key)
                    unique.append(list(key))
            groups[cr] = unique
        else:
            groups[cr] = raw

    two_groups: list[list[int]] = []
    for chosen in combinations(range(8), 2):
        flag = np.zeros(8, dtype=np.uint8)
        flag[list(chosen)] = 1
        row_out: list[int] = []
        for codeword in codebook8:
            changed = np.flatnonzero(
                flag.astype(np.int16) - codeword.astype(np.int16)
            )
            if changed.size == 2:
                row_out.extend(int(value) for value in changed)
        if row_out:
            two_groups.append(row_out)
    return _Common(
        cr2_group=np.asarray(groups[2], dtype=np.int64),
        cr3_group=np.asarray(groups[3], dtype=np.int64),
        cr4_group=np.asarray(groups[4], dtype=np.int64),
        cr4_two_group=np.asarray(two_groups, dtype=np.int64),
    )


CODEBOOK8 = _codebook(4)
COMMON = _generate_common(CODEBOOK8)


def _repair_with_one_column(
    received: np.ndarray,
    corrected: np.ndarray,
    diff1_locations: np.ndarray,
    diff2_rows: np.ndarray,
    codebook: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    out = corrected.copy()
    fixed = np.zeros(diff2_rows.size, dtype=bool)
    other = np.full(diff2_rows.size, -1, dtype=np.int64)
    for output_index, row_index in enumerate(diff2_rows):
        trial = received[int(row_index)].copy()
        trial[diff1_locations] ^= 1
        distances = np.sum(np.abs(codebook.astype(np.int16) - trial), axis=1)
        matches = np.flatnonzero(distances == 1)
        if matches.size:
            codeword = codebook[int(matches[0])]
            fixed[output_index] = True
            out[int(row_index)] = codeword
            changed = np.flatnonzero(trial != codeword)
            if changed.size:
                other[output_index] = int(changed[0])
    return out, fixed, other


def _cr4_generated_selections(locations: np.ndarray) -> list[list[int]]:
    loc = [int(value) for value in locations]
    if len(loc) == 3:
        loc_set = set(loc)
        for group in COMMON.cr4_group:
            if loc_set.issubset(set(int(value) for value in group)):
                loc = [int(value) for value in group]
                break
    if len(loc) == 4:
        return [list(item) for item in combinations(loc, 3)]
    return []


def _decode_block_cr4(
    received: np.ndarray,
    corrected: np.ndarray,
    known_bad: np.ndarray,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    difference = corrected.astype(np.int16) - received.astype(np.int16)
    _, diff1_rows, diff2_rows, diff1_locations = _difference_structure(
        corrected, received, known_bad
    )

    for attempted_errors in range(5):
        candidate_locations: list[np.ndarray] = []
        candidates: list[np.ndarray] = []
        changed_columns = np.flatnonzero(np.sum(np.abs(difference), axis=0))

        if attempted_errors == 0 and changed_columns.size == 0:
            candidates.append(corrected.copy())

        if attempted_errors == 1 and changed_columns.size <= 1:
            candidate_locations.append(changed_columns.copy())
            candidates.append(corrected.copy())

        if attempted_errors == 2:
            if diff1_locations.size == 2:
                good, matrix = _check_selection(CODEBOOK8, diff1_locations, received)
                if good:
                    candidate_locations.append(diff1_locations.copy())
                    candidates.append(matrix)
            elif diff1_locations.size == 1:
                matrix, fixed, other = _repair_with_one_column(
                    received, corrected, diff1_locations, diff2_rows, CODEBOOK8
                )
                valid_other = other[fixed]
                if np.all(fixed) and valid_other.size and np.unique(valid_other).size == 1:
                    candidate_locations.append(
                        np.asarray([int(diff1_locations[0]), int(valid_other[0])])
                    )
                    candidates.append(matrix)
            elif diff1_locations.size == 0 and diff2_rows.size:
                flags: list[np.ndarray] = []
                for row_index in diff2_rows:
                    flag = (difference[int(row_index)] != 0).astype(np.uint8)
                    if not any(np.array_equal(flag, old) for old in flags):
                        flags.append(flag)
                first_pair = np.flatnonzero(flags[0])
                group = next(
                    (
                        row
                        for row in COMMON.cr4_two_group
                        if row.size >= 2 and np.array_equal(row[:2], first_pair)
                    ),
                    None,
                )
                if group is not None and group.size >= 8:
                    theoretical: list[np.ndarray] = []
                    for index in range(4):
                        flag = np.zeros(8, dtype=np.uint8)
                        flag[group[2 * index : 2 * index + 2]] = 1
                        theoretical.append(flag)
                    if all(any(np.array_equal(flag, row) for row in theoretical) for flag in flags):
                        for flag in theoretical:
                            matrix = received.copy()
                            matrix[diff2_rows] ^= flag
                            candidate_locations.append(np.flatnonzero(flag))
                            candidates.append(matrix)

        if attempted_errors == 3:
            selections: list[list[int]] = []
            if diff1_locations.size == 1:
                _, fixed, other = _repair_with_one_column(
                    received, corrected, diff1_locations, diff2_rows, CODEBOOK8
                )
                extended = np.unique(
                    np.concatenate([diff1_locations, other[fixed & (other >= 0)]])
                )
                selections = _cr4_generated_selections(extended)
            elif diff1_locations.size == 2:
                for column in range(received.shape[1]):
                    if column not in set(int(value) for value in diff1_locations):
                        selections.append([*map(int, diff1_locations), column])
            elif 3 <= diff1_locations.size <= 4:
                selections = _cr4_generated_selections(np.sort(diff1_locations))

            for selection in selections:
                good, matrix = _check_selection(CODEBOOK8, selection, received)
                if good:
                    candidate_locations.append(np.asarray(sorted(selection)))
                    candidates.append(matrix)

            if diff1_locations.size == 2 and len(candidate_locations) == 2:
                extras = [
                    list(set(map(int, row)) - set(map(int, diff1_locations)))
                    for row in candidate_locations
                ]
                flat = [value for row in extras for value in row]
                if len(flat) == 2:
                    retry = [
                        [int(diff1_locations[0]), *flat],
                        [int(diff1_locations[1]), *flat],
                    ]
                    for selection in retry:
                        good, matrix = _check_selection(CODEBOOK8, selection, received)
                        if good:
                            candidate_locations.append(np.asarray(sorted(selection)))
                            candidates.append(matrix)

        if candidates:
            return candidates, candidate_locations
    return [], []


def _decode_block_cr1(received: np.ndarray) -> tuple[list[np.ndarray], list[np.ndarray]]:
    syndrome = (np.sum(received[:, :4], axis=1) & 1) != received[:, 4]
    if not np.any(syndrome):
        return [received.copy()], [np.asarray([], dtype=np.int64)]
    candidates: list[np.ndarray] = []
    locations: list[np.ndarray] = []
    for column in range(5):
        other = [value for value in range(5) if value != column]
        matrix = received.copy()
        matrix[:, column] = np.sum(received[:, other], axis=1) & 1
        candidates.append(matrix)
        locations.append(np.asarray([column], dtype=np.int64))
    return candidates, locations


def _decode_block_cr2(
    received: np.ndarray,
    corrected: np.ndarray,
    known_bad: np.ndarray,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    _, _, _, locations = _difference_structure(corrected, received, known_bad)
    expanded = set(int(value) for value in locations)
    for value in list(expanded):
        rows = COMMON.cr2_group[COMMON.cr2_group[:, 0] == value]
        expanded.update(int(row[1]) for row in rows)
    expanded_values = np.asarray(sorted(expanded), dtype=np.int64)
    if expanded_values.size == 0:
        return [received.copy()], [np.asarray([], dtype=np.int64)]
    candidates: list[np.ndarray] = []
    selected: list[np.ndarray] = []
    if expanded_values.size == 2 and any(
        np.array_equal(expanded_values, row) for row in COMMON.cr2_group
    ):
        for selection in combinations(map(int, expanded_values), 1):
            good, matrix = _check_selection(
                _codebook(2), list(selection), received
            )
            if good:
                candidates.append(matrix)
                selected.append(np.asarray(selection, dtype=np.int64))
    return candidates, selected


def _decode_block_cr3(
    received: np.ndarray,
    corrected: np.ndarray,
    known_bad: np.ndarray,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    difference = corrected.astype(np.int16) - received.astype(np.int16)
    _, _, _, locations = _difference_structure(corrected, received, known_bad)
    changed = np.flatnonzero(np.sum(np.abs(difference), axis=0))
    if changed.size <= 1:
        return [corrected.copy()], [changed]
    if locations.size == 2:
        for group in COMMON.cr3_group:
            if np.array_equal(np.sort(locations), group[:2]):
                locations = group.copy()
                break
    candidates: list[np.ndarray] = []
    selected: list[np.ndarray] = []
    if locations.size == 3:
        for selection in combinations(map(int, locations), 2):
            good, matrix = _check_selection(
                _codebook(3), list(selection), received
            )
            if good:
                candidates.append(matrix)
                selected.append(np.asarray(selection, dtype=np.int64))
    return candidates, selected


def _header_checksum_ok(nibbles: list[int]) -> bool:
    if len(nibbles) < 5:
        return False
    bits = np.asarray(
        [bit for nibble in nibbles[:3] for bit in int_to_bits(int(nibble), 4)],
        dtype=np.uint8,
    )
    calculated = np.sum(HEADER_CHECKSUM_MATRIX * bits[None, :], axis=1) & 1
    received = np.asarray(
        [
            *[(int(nibbles[4]) >> index) & 1 for index in range(4)],
            int(nibbles[3]) & 1,
        ],
        dtype=np.uint8,
    )
    return bool(np.array_equal(calculated, received))


class TnBBECDecoder:
    """Stateful decoder matching one MATLAB TnBDecode batch invocation."""

    CRC_ATTEMPT_MAX = (25, 16, 16, 16)

    def __init__(self, *, random_seed: int = 0):
        self.random = np.random.RandomState(int(random_seed))

    def _decode_header(
        self,
        symbol_values: list[int],
        cfg,
    ) -> tuple[list[int], int, bool, int, np.ndarray] | None:
        if len(symbol_values) < 8:
            return None
        matrix = _deinterleave_matrix(
            symbol_values[:8],
            sf=cfg.sf,
            sf_app=cfg.sf - 2,
            codeword_width=8,
        )
        corrected = _nearest_codewords(matrix, 4)
        candidates, _ = _decode_block_cr4(
            matrix, corrected, np.asarray([], dtype=np.int64)
        )
        for candidate in candidates[:8]:
            nibbles = [_bits_to_int(row[:4]) for row in candidate]
            if not _header_checksum_ok(nibbles):
                continue
            payload_length = int(nibbles[0]) * 16 + int(nibbles[1])
            crc_enabled = bool(int(nibbles[2]) & 1)
            coding_rate = int(nibbles[2]) >> 1
            if (
                payload_length <= 0
                or payload_length > 32
                or coding_rate < 1
                or coding_rate > 4
            ):
                continue
            return nibbles[:5], payload_length, crc_enabled, coding_rate, candidate[5:]
        return None

    def decode(self, symbol_bins: list[int], cfg) -> TnBBECResult:
        if len(symbol_bins) < int(cfg.payload_symbol_count):
            return TnBBECResult(
                b"", False, [], 0, 0, False, 0, 0, 0, "not_enough_symbols"
            )
        inverse = gray_inverse_map(cfg)
        symbol_values = [
            int(inverse.get(int(value) % cfg.m, 0))
            for value in symbol_bins[: int(cfg.payload_symbol_count)]
        ]
        header = self._decode_header(symbol_values, cfg)
        if header is None:
            return TnBBECResult(
                b"", False, [], 0, 0, False, 0, 0, 0, "header_bec_failed"
            )
        header_nibbles, payload_length, crc_enabled, cr, header_payload = header

        received_parts: list[np.ndarray] = [header_payload]
        index = 8
        while index + cr + 4 <= len(symbol_values):
            received_parts.append(
                _deinterleave_matrix(
                    symbol_values[index : index + cr + 4],
                    sf=cfg.sf,
                    sf_app=cfg.sf,
                    codeword_width=cr + 4,
                )
            )
            index += cr + 4
        if len(received_parts) == 1:
            return TnBBECResult(
                b"",
                False,
                header_nibbles,
                cr,
                payload_length,
                crc_enabled,
                0,
                0,
                0,
                "not_enough_payload_blocks",
            )

        width = cr + 4
        first = np.zeros((header_payload.shape[0], width), dtype=np.uint8)
        first[:, : min(width, header_payload.shape[1])] = header_payload[
            :, : min(width, header_payload.shape[1])
        ]
        received = np.vstack([first, *received_parts[1:]]).astype(np.uint8)
        corrected = (
            received.copy() if cr == 1 else _nearest_codewords(received, cr)
        )
        carry_rows = int(header_payload.shape[0])
        block_count = (received.shape[0] - 1) // int(cfg.sf)
        block_candidates: list[list[np.ndarray]] = []
        block_locations: list[list[np.ndarray]] = []
        for block_index in range(block_count):
            begin = carry_rows + block_index * int(cfg.sf)
            end = begin + int(cfg.sf)
            if end > received.shape[0]:
                break
            rcv = received[begin:end]
            cor = corrected[begin:end]
            known_bad = np.asarray([], dtype=np.int64)
            if cr == 1:
                candidates, locations = _decode_block_cr1(rcv)
            elif cr == 2:
                candidates, locations = _decode_block_cr2(rcv, cor, known_bad)
            elif cr == 3:
                candidates, locations = _decode_block_cr3(rcv, cor, known_bad)
            else:
                candidates, locations = _decode_block_cr4(rcv, cor, known_bad)
            if not candidates:
                return TnBBECResult(
                    b"",
                    False,
                    header_nibbles,
                    cr,
                    payload_length,
                    crc_enabled,
                    0,
                    0,
                    0,
                    "payload_bec_no_candidate",
                )
            block_candidates.append(candidates)
            block_locations.append(locations)

        if not block_candidates:
            return TnBBECResult(
                b"",
                False,
                header_nibbles,
                cr,
                payload_length,
                crc_enabled,
                0,
                0,
                0,
                "payload_bec_no_block",
            )

        schedules = list(product(*(range(len(rows)) for rows in block_candidates)))
        total_schedules = len(schedules)
        cap = self.CRC_ATTEMPT_MAX[cr - 1]
        if total_schedules <= cap:
            selected_schedule_indices = set(range(total_schedules))
        else:
            selected_schedule_indices = set(
                int(value) for value in self.random.permutation(total_schedules)[:cap]
            )

        attempts = 0
        for schedule_index, schedule in enumerate(schedules):
            if schedule_index not in selected_schedule_indices:
                continue
            attempts += 1
            trial = corrected.copy()
            corrected_rows: set[int] = set()
            for block_index, choice in enumerate(schedule):
                begin = carry_rows + block_index * int(cfg.sf)
                end = begin + int(cfg.sf)
                trial[begin:end] = block_candidates[block_index][choice]
                if choice < len(block_locations[block_index]):
                    corrected_rows.update(
                        int(value)
                        for value in block_locations[block_index][choice]
                    )

            nibbles = [_bits_to_int(row[:4]) for row in trial]
            byte_values = bytes(
                (int(nibbles[offset]) & 0x0F)
                | ((int(nibbles[offset + 1]) & 0x0F) << 4)
                for offset in range(0, len(nibbles) - 1, 2)
            )
            crc_bytes = 2 if crc_enabled else 0
            required = payload_length + crc_bytes
            if len(byte_values) < required:
                continue
            payload = bytes(
                np.frombuffer(byte_values[:payload_length], dtype=np.uint8)
                ^ WHITENING_SEQ[:payload_length]
            )
            if crc_enabled:
                decoded_crc = int.from_bytes(
                    byte_values[payload_length : payload_length + 2], "little"
                )
                crc_ok = decoded_crc == lora_payload_crc(payload)
            else:
                crc_ok = True
            if crc_ok:
                changed = np.any(trial != corrected, axis=1)
                return TnBBECResult(
                    payload,
                    True,
                    header_nibbles,
                    cr,
                    payload_length,
                    crc_enabled,
                    attempts,
                    total_schedules,
                    int(np.count_nonzero(changed)),
                    "ok",
                )

        return TnBBECResult(
            b"",
            False,
            header_nibbles,
            cr,
            payload_length,
            crc_enabled,
            attempts,
            total_schedules,
            0,
            "payload_crc_failed_after_bec",
        )
