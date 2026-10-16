"""Versioned selection budgets shared by extraction and frozen-data verification."""

PUBLIC_MAPPING_LIMITS = {
    "conservative-exact-generics-v1": (10, 10),
    "conservative-exact-generics-v2": (30, 50),
}


def public_mapping_limits(mapping_version):
    if not isinstance(mapping_version, str) or mapping_version not in PUBLIC_MAPPING_LIMITS:
        raise ValueError("Unsupported frozen extraction mapping.")
    return PUBLIC_MAPPING_LIMITS[mapping_version]
