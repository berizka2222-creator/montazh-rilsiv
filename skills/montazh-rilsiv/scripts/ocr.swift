// Text on screen with its boxes (macOS Vision, accurate mode, uk / en / ru), nothing leaves the Mac.
// Image paths one per line on stdin. For every image prints "#<index>" and then one line per text line:
//   x y w h<TAB>text      (x, y, w, h in 0..1 of the frame, y from the TOP)
// and, per word inside it, "  ~ x y w h<TAB>word" so a single ID or sum inside a long line can be boxed alone.
import Foundation
import Vision
import AppKit

var i = 0
while let path = readLine() {
    print("#\(i)"); i += 1
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    if #available(macOS 13.0, *) { req.recognitionLanguages = ["uk-UA", "en-US", "ru-RU"] }
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    for obs in req.results ?? [] {
        guard let cand = obs.topCandidates(1).first else { continue }
        let b = obs.boundingBox
        print(String(format: "%.4f %.4f %.4f %.4f\t", b.minX, 1 - b.maxY, b.width, b.height) + cand.string.replacingOccurrences(of: "\n", with: " "))
        let s = cand.string
        s.enumerateSubstrings(in: s.startIndex..<s.endIndex, options: .byWords) { word, range, _, _ in
            guard let w = word, let r = try? cand.boundingBox(for: range) else { return }
            let bb = r.boundingBox
            print(String(format: "  ~ %.4f %.4f %.4f %.4f\t", bb.minX, 1 - bb.maxY, bb.width, bb.height) + w)
        }
    }
}
