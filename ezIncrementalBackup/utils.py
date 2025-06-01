def is_excluded_path(rel_path, exclude_dirs):
    rel_path = rel_path.replace("\\", "/")
    return any(rel_path == ex or rel_path.startswith(ex + "/") for ex in exclude_dirs) 