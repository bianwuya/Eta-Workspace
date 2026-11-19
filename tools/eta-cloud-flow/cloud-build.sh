#!/bin/bash
set -euo pipefail
source_kind=${1:?archive|wslgit}
source_archive_sha=''
case "$source_kind" in
    archive)
        archive=${2:?source tar archive}
        commit=${3:?source commit}
        tree=${4:?source tree}
        source_archive_sha=${5:?source archive SHA256}
        name=${6:?run name}
        mode=${7:?compile|test|assemble|delivery}
        connectivity=${8:-offline}
        out=${9:?output directory}
        ;;
    wslgit)
        source_git=${2:?Linux native source mirror}
        commit=${3:?source commit}
        tree=${4:?source tree}
        name=${5:?run name}
        mode=${6:?compile|test|assemble|delivery}
        connectivity=${7:-offline}
        out=${8:?output directory}
        [[ "$source_git" == /opt/eta/sources/*.git ]] || { echo 'Source mirror must be inside /opt/eta/sources' >&2; exit 2; }
        ;;
    *) echo 'Invalid source kind' >&2; exit 2;;
esac
case "$name" in *[!a-zA-Z0-9._-]*|'') echo 'Invalid run name' >&2; exit 2;; esac
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid full commit SHA' >&2; exit 2; }
[[ "$tree" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid source tree SHA' >&2; exit 2; }
if [[ "$source_kind" == archive && ! "$source_archive_sha" =~ ^[0-9a-f]{64}$ ]]; then
    echo 'Invalid source archive SHA256' >&2
    exit 2
fi
case "$mode" in compile|test|assemble|delivery) ;; *) echo 'Invalid mode' >&2; exit 2;; esac
case "$connectivity" in online|offline) ;; *) echo 'Invalid connectivity' >&2; exit 2;; esac
command -v flock >/dev/null || { echo 'flock is required' >&2; exit 2; }

export JAVA_HOME=/opt/eta/runtimes/jdk-25.0.2
export PATH="$JAVA_HOME/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export GRADLE_USER_HOME=/opt/eta/cache
export ANDROID_HOME=/opt/eta/sdk
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export ANDROID_USER_HOME=/opt/eta/home/android
export HOME=/opt/eta/home
export TMPDIR=/opt/eta/tmp
unset ETA_RELEASE_STORE_FILE ETA_RELEASE_STORE_PASSWORD ETA_RELEASE_KEY_ALIAS ETA_RELEASE_KEY_PASSWORD
mkdir -p "$out" "$ANDROID_USER_HOME" "$TMPDIR" /opt/eta/locks /opt/eta/trees

if [[ "$source_kind" == archive ]]; then
    printf '%s  %s\n' "$source_archive_sha" "$archive" | sha256sum -c -
fi
dst=/opt/eta/trees/eta-cloud-v2-$commit
lock=/opt/eta/locks/eta-cloud-build.lock
exec 9>"$lock"
if ! flock -w 3600 9; then
    echo 'Another cloud-flow build is still active' >&2
    exit 75
fi

fresh=0
if [[ ! -e "$dst" ]]; then
    fresh=1
    mkdir "$dst"
    if [[ "$source_kind" == wslgit ]]; then
        git -C "$source_git" archive "$commit" | tar -C "$dst" -xf -
    else
        tar -C "$dst" -xf "$archive"
    fi
fi
if [[ ! -d "$dst/app" ]]; then
    echo "Refusing an invalid source snapshot: $dst" >&2
    exit 3
fi
cd "$dst"
source_manifest() {
    find . \( -path './build' -o -path './app/build' -o -path './.gradle' -o -path './.kotlin' \) -prune -o \
        -type f ! -name 'local.properties' ! -name '.eta-source-*' \
        -printf '%P\0' | sort -z | xargs -0 -r sha256sum
}
if [[ $fresh -eq 1 ]]; then
    printf '%s\n' "$commit" > .eta-source-commit
    printf '%s\n' "$tree" > .eta-source-tree
    if [[ "$source_kind" == archive ]]; then
        printf '%s\n' "$source_archive_sha" > .eta-source-archive-sha256
    fi
    source_manifest > .eta-source-manifest
else
    [[ $(cat .eta-source-commit 2>/dev/null) == "$commit" ]] || { echo 'Snapshot commit marker mismatch' >&2; exit 3; }
    [[ $(cat .eta-source-tree 2>/dev/null) == "$tree" ]] || { echo 'Snapshot tree marker mismatch' >&2; exit 3; }
    if ! source_manifest | diff -u .eta-source-manifest -; then
        echo "Refusing to overwrite a changed Linux snapshot: $dst" >&2
        exit 3
    fi
fi
printf 'sdk.dir=/opt/eta/sdk\n' > "$dst/local.properties"
options=(-I /mnt/f/eta/02-工程知识库/plans/20261112-测试环境与Git权限修复/linux.init.gradle
 --no-configuration-cache --build-cache --no-daemon --max-workers=1 --console=plain
 -Pkotlin.compiler.execution.strategy=in-process
 -Dorg.gradle.java.installations.auto-download=false
 -Dorg.gradle.java.installations.paths=/opt/eta/runtimes/jdk-25.0.2
 '-Dorg.gradle.jvmargs=-Xmx4g -XX:MaxMetaspaceSize=1g -Dfile.encoding=UTF-8')
if [[ "$connectivity" == offline ]]; then options+=(--offline); fi
case "$mode" in
    compile) tasks=(:app:compileDebugKotlin);;
    test) tasks=(:app:compileDebugKotlin :app:testDebugUnitTest :app:lintDebug);;
    assemble) tasks=(:app:compileDebugKotlin :app:assembleDebug :app:assembleRelease);;
    delivery) tasks=(:app:compileDebugKotlin :app:testDebugUnitTest :app:lintDebug :app:assembleDebug :app:assembleRelease);;
esac

started=$(date +%s)
date -Is > "$out/started-at"
printf '%s\n' "$commit" > "$out/source-commit"
printf '%s\n' "$tree" > "$out/source-tree"
printf '%s\n' "$source_kind" > "$out/source-kind"
printf '%q ' /opt/eta/runtimes/gradle-9.7.1/bin/gradle "${options[@]}" "-Peta.buildMetadata=$commit" "${tasks[@]}" > "$out/command.txt"
set +e
/opt/eta/runtimes/gradle-9.7.1/bin/gradle "${options[@]}" "-Peta.buildMetadata=$commit" "${tasks[@]}" > "$out/gradle.log" 2>&1
code=$?
set -e
ended=$(date +%s)
printf '%s\n' "$code" > "$out/exit-code"
date -Is > "$out/ended-at"
printf '%s\n' "$((ended-started))" > "$out/duration-seconds"
if [[ $code -ne 0 ]]; then
    tail -n 50 "$out/gradle.log"
    exit "$code"
fi

if [[ "$mode" == assemble || "$mode" == delivery ]]; then
    for variant in debug release; do
        mapfile -t apks < <(find "app/build/outputs/apk/$variant" -maxdepth 1 -type f -name 'Eta-v*.apk' | sort)
        if [[ ${#apks[@]} -ne 1 ]]; then
            echo "Expected one $variant APK, found ${#apks[@]}" >&2
            exit 4
        fi
        if [[ "$variant" == debug ]]; then
            cp -- "${apks[0]}" "$out/debug.apk"
        else
            cp -- "${apks[0]}" "$out/release-unsigned.apk"
        fi
    done
    (cd "$out" && sha256sum debug.apk release-unsigned.apk > artifact-input-hashes.txt)
fi
printf 'status=passed\ncommit=%s\nmode=%s\ndurationSeconds=%s\n' "$commit" "$mode" "$((ended-started))" > "$out/build-result.txt"
tail -n 35 "$out/gradle.log"
