import os
from pathlib import Path
from typing import Set, Tuple

from git import InvalidGitRepositoryError, Repo


class GitUtil:
    def __init__(self, repo: Repo = None):
        if not repo:
            try:
                self.repo = Repo(Path.cwd(), search_parent_directories=True)
            except InvalidGitRepositoryError:
                raise InvalidGitRepositoryError("Unable to find Repository from current working directory - aboring")
        else:
            self.repo = repo

    def modified_files(self, prev_ver: str = 'master', committed_only: bool = False,
                       staged_only: bool = False) -> Set[Path]:
        """Gets all the files that are recognized by git as modified against the prev_ver.

        Args:
            prev_ver (str): The base branch against which the comparison is made.
            committed_only (bool): Whether to return only committed files.
            staged_only (bool): Whether to return only staged files.

        Returns:
            Set: A set of Paths to the modified files.
        """
        prev_ver = prev_ver.replace('origin/', '')

        # get all renamed files - some of these can be identified as modified by git,
        # but we want to identify them as renamed - so will remove them from the returned files.
        renamed = {item[0] for item in self.renamed_files(prev_ver, committed_only, staged_only)}

        deleted = self.deleted_files(prev_ver, committed_only, staged_only)

        # get all committed files identified as modified which are changed from prev_ver.
        # this can result in extra files identified which were not touched on this branch.
        committed = {Path(os.path.join(item.a_path)) for item
                     in self.repo.remote().refs[prev_ver].commit.diff(
            self.repo.active_branch).iter_change_type('M')}

        # identify all files that were touched on this branch regardless of status
        # intersect these with all the committed files to identify the committed modified files.
        all_branch_changed_files = self._get_all_changed_files(prev_ver)
        committed = committed.intersection(all_branch_changed_files)

        if committed_only:
            return committed - renamed - deleted

        # get all untracked modified files
        untracked = self._get_untracked_files('M')

        # get all the files that are staged on the branch and identified as modified.
        staged = {Path(os.path.join(item.a_path)) for item
                  in self.repo.head.commit.diff().iter_change_type('M')}.union(untracked)

        # If a file is Added in regards to prev_ver
        # and is then modified locally after being committed - it is identified as modified
        # but we want to identify the file as Added (its actual status against prev_ver) -
        # so will remove it from the staged modified files.
        committed_added = {Path(os.path.join(item.a_path)) for item in self.repo.remote().refs[prev_ver].commit.diff(
            self.repo.active_branch).iter_change_type('A')}

        staged = staged - committed_added

        if staged_only:
            return staged - renamed - deleted

        return staged.union(committed) - renamed - deleted

    def added_files(self, prev_ver: str = 'master', committed_only: bool = False,
                    staged_only: bool = False) -> Set[Path]:
        """Gets all the files that are recognized by git as added against the prev_ver.

        Args:
            prev_ver (str): The base branch against which the comparison is made.
            committed_only (bool): Whether to return only committed files.
            staged_only (bool): Whether to return only staged files.

        Returns:
            Set: A set of Paths to the added files.
        """
        prev_ver = prev_ver.replace('origin/', '')

        deleted = self.deleted_files(prev_ver, committed_only, staged_only)

        # get all committed files identified as added which are changed from prev_ver.
        # this can result in extra files identified which were not touched on this branch.
        committed = {Path(os.path.join(item.a_path)) for item
                     in self.repo.remote().refs[prev_ver].commit.diff(
            self.repo.active_branch).iter_change_type('A')}

        # identify all files that were touched on this branch regardless of status
        # intersect these with all the committed files to identify the committed added files.
        all_branch_changed_files = self._get_all_changed_files(prev_ver)
        committed = committed.intersection(all_branch_changed_files)

        if committed_only:
            return committed - deleted

        # get all untracked added files
        untracked = self._get_untracked_files('A')

        # get all the files that are staged on the branch and identified as added.
        staged = {Path(os.path.join(item.a_path)) for item in
                  self.repo.head.commit.diff().iter_change_type('A')}.union(untracked)

        # If a file is Added in regards to prev_ver
        # and is then modified locally after being committed - it is identified as modified
        # but we want to identify the file as Added (its actual status against prev_ver) -
        # so will added it from the staged added files.
        committed_added_locally_modified = {Path(os.path.join(item.a_path)) for item in
                                            self.repo.head.commit.diff().iter_change_type('M')}.intersection(committed)

        staged = staged.union(committed_added_locally_modified)

        if staged_only:
            return staged - deleted

        return staged.union(committed) - deleted

    def deleted_files(self, prev_ver: str = 'master', committed_only: bool = False,
                      staged_only: bool = False) -> Set[Path]:
        """Gets all the files that are recognized by git as deleted against the prev_ver.

        Args:
            prev_ver (str): The base branch against which the comparison is made.
            committed_only (bool): Whether to return only committed files.
            staged_only (bool): Whether to return only staged files.

        Returns:
            Set: A set of Paths to the deleted files.
        """
        prev_ver = prev_ver.replace('origin/', '')

        # get all committed files identified as added which are changed from prev_ver.
        # this can result in extra files identified which were not touched on this branch.
        committed = {Path(os.path.join(item.a_path)) for item
                     in self.repo.remote().refs[prev_ver].commit.diff(
            self.repo.active_branch).iter_change_type('D')}

        # identify all files that were touched on this branch regardless of status
        # intersect these with all the committed files to identify the committed added files.
        all_branch_changed_files = self._get_all_changed_files(prev_ver)
        committed = committed.intersection(all_branch_changed_files)

        if committed_only:
            return committed

        # get all untracked deleted files
        untracked = self._get_untracked_files('D')

        # get all the files that are staged on the branch and identified as added.
        staged = {Path(os.path.join(item.a_path)) for item in
                  self.repo.head.commit.diff().iter_change_type('D')}.union(untracked)

        if staged_only:
            return staged

        return staged.union(committed)

    def renamed_files(self, prev_ver: str = 'master', committed_only: bool = False,
                      staged_only: bool = False) -> Set[Tuple[Path, Path]]:
        """Gets all the files that are recognized by git as renamed against the prev_ver.

        Args:
            prev_ver (str): The base branch against which the comparison is made.
            committed_only (bool): Whether to return only committed files.
            staged_only (bool): Whether to return only staged files.

        Returns:
            Set: A set of Tuples of Paths to the renamed files -
            first element being the old file path and the second is the new.
        """
        prev_ver = prev_ver.replace('origin/', '')

        deleted = self.deleted_files(prev_ver, committed_only, staged_only)

        # get all committed files identified as renamed which are changed from prev_ver.
        # this can result in extra files identified which were not touched on this branch.
        committed = {(Path(item.a_path), Path(item.b_path)) for item
                     in self.repo.remote().refs[prev_ver].commit.diff(
            self.repo.active_branch).iter_change_type('R')}

        # identify all files that were touched on this branch regardless of status
        # intersect these with all the committed files to identify the committed added files.
        all_branch_changed_files = self._get_all_changed_files(prev_ver)
        committed = {tuple_item for tuple_item in committed
                     if (tuple_item[1] in all_branch_changed_files and tuple_item[1] not in deleted)}

        if committed_only:
            return committed

        # get all untracked renamed files
        untracked = self._get_untracked_files('R')

        # get all the files that are staged on the branch and identified as renamed.
        staged = {(Path(item.a_path), Path(item.b_path)) for item
                  in self.repo.head.commit.diff().iter_change_type('R')}.union(untracked)

        if staged_only:
            return staged

        return staged.union(committed)

    def _get_untracked_files(self, requested_status: str) -> set:
        """return all untracked files of the given requested status.

        Args:
            requested_status (str): M, A, R, D - the git status to return

        Returns:
            Set: of path strings which include the untracked files of a certain status.
        """
        git_status = self.repo.git.status('--short', '-u').split('\n')

        # in case there are no local changes - return
        if git_status == ['']:
            return set()

        extracted_paths = set()
        for line in git_status:
            line = line.strip()
            file_status = line.split()[0].upper() if not line.startswith('?') else 'A'
            if file_status == requested_status:
                if requested_status == 'R':
                    extracted_paths.add((Path(line.split()[-2]), Path(line.split()[-1])))
                else:
                    extracted_paths.add(Path(line.split()[-1]))  # type: ignore

        return extracted_paths

    def _get_all_changed_files(self, prev_ver: str) -> Set[Path]:
        """Get all the files changed in the current branch without status distinction.

        Args:
            prev_ver (str): The base branch against which the comparison is made.

        Returns:
            Set: of Paths to files changed in the current branch.
        """
        origin_prev_ver = prev_ver if prev_ver.startswith('origin/') else f"origin/{prev_ver}"
        return {Path(os.path.join(item)) for item
                in self.repo.git.diff('--name-only',
                                      f'{origin_prev_ver}...{self.repo.active_branch}').split('\n')}
