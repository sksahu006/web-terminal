// Deliberately obfuscated - the point of the lab is to read through this and
// figure out the transform by hand, then reimplement it (bash/python/whatever)
// instead of ever running this file.
function _0x1a(s) {
    var _0xr = s.split('').reverse().join('');
    var _0xo = '';
    for (var _0xi = 0; _0xi < _0xr.length; _0xi++) {
        _0xo += String.fromCharCode(_0xr.charCodeAt(_0xi) + 3);
    }
    return btoa(_0xo);
}

function computeToken(seed) {
    return _0x1a(seed);
}
