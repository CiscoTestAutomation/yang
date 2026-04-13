# Generated for direct meson-python packaging
project(
  'yang.ncdiff',
  meson_version: '>=1.10.0',
)

fs = import('fs')
pymod = import('python')
package_folder = 'src'
py = pymod.find_installation(pure: true)
package_root = meson.project_source_root() / package_folder
package_root_prefix = package_root + '/'
git_prog = find_program('git')

# File extensions to include from tracked files under src/.
# Expected values are bare extensions without a leading dot, for example: 'py', 'yaml', 'json'.
include_extensions = ['py', 'txt']
# Exact filenames to include when they do not rely on an extension match.
# Expected values are basename matches, for example: 'ssh_host_key', 'runAll'.
include_files = []
# Substring markers for tracked paths that should still be ignored if they ever appear.
# Expected values are path fragments, for example: '/generated/', '/vendor/', '.egg-info/'.
ignored_path_markers = []

all_tracked_files = run_command(
  git_prog,
  'ls-files',
  package_folder,
  check: true,
).stdout().strip().split('\n')

foreach relpath : all_tracked_files
  if relpath == ''
    continue
  endif

  skip_path = false
  foreach marker : ignored_path_markers
    if relpath.contains(marker)
      skip_path = true
      break
    endif
  endforeach
  if skip_path
    continue
  endif

  path_has_included_ext = false
  foreach extension : include_extensions
    if relpath.endswith('.' + extension)
      path_has_included_ext = true
      break
    endif
  endforeach

  if not path_has_included_ext
    filename = fs.name(relpath)
    foreach include_name : include_files
      if filename == include_name
        path_has_included_ext = true
        break
      endif
    endforeach
  endif

  if not path_has_included_ext
    continue
  endif

  path = meson.project_source_root() / relpath
  relative_path = path.replace(package_root_prefix, '')
  install_target_dir = py.get_install_dir()
  relative_parent = fs.parent(relative_path)

  if relative_parent != '.'
    install_target_dir = install_target_dir / relative_parent
  endif

  install_data(
    path,
    install_dir: install_target_dir,
  )
endforeach
