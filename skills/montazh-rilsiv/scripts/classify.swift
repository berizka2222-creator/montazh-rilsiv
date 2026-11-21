// What is in a picture, on the Mac (Vision image classification, ~1300 English labels: beach, laptop, coffee, dog...).
// Image paths one per line on stdin; prints one line per image: "label:conf label:conf ..." (best first) or "none".
// Only labels Vision itself calls reliable (70 % precision at its recall curve) and confidence >= 0.1.
import Foundation
import Vision
import AppKit

while let path = readLine() {
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("none"); continue }
    let req = VNClassifyImageRequest()
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    let good = (req.results ?? []).filter { $0.confidence >= 0.1 && $0.hasMinimumPrecision(0.7, forRecall: 0.01) }
        .sorted { $0.confidence > $1.confidence }.prefix(12)
    print(good.isEmpty ? "none" : good.map { String(format: "%@:%.2f", $0.identifier, $0.confidence) }.joined(separator: " "))
}
