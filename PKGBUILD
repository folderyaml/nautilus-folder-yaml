pkgname=nautilus-folder-yaml
pkgver=0.5.3
pkgrel=1
pkgdesc='nautilus 插件：用 .folder.yaml 给文件夹和文件加描述'
arch=('any')
url='https://github.com/folderyaml/nautilus-folder-yaml'
license=('MIT')
depends=('nautilus-python' 'python-ruamel-yaml')
# 只有插件本体与许可证进包；GitHub 的 tag 归档里还带测试和文档
source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')
install="$pkgname.install"

package() {
  install -Dm644 "$pkgname-$pkgver/nautilus-folder-yaml.py" \
    "$pkgdir/usr/share/nautilus-python/extensions/nautilus-folder-yaml.py"
  install -Dm644 "$pkgname-$pkgver/LICENSE" \
    "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
