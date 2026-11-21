// Head pose and eyes per image (macOS Vision, nothing leaves the Mac). Image paths come one per line on stdin.
// Prints one line per image: "yaw pitch roll eyeOpen pupilDown" or "none".
//   yaw / pitch / roll: degrees (pitch needs macOS 12+, else 0)
//   eyeOpen: eye height / eye width, the mean of both eyes (open ~0.25-0.4, closed < ~0.12)
//   pupilDown: how far the pupils sit below the eye's centre, in eye heights (looking down at a script > ~0.15)
import Foundation
import Vision
import AppKit

func box(_ r: VNFaceLandmarkRegion2D?) -> (CGFloat, CGFloat, CGFloat, CGFloat)? {
    guard let p = r?.normalizedPoints, !p.isEmpty else { return nil }
    let xs = p.map { $0.x }, ys = p.map { $0.y }
    return (xs.min()!, xs.max()!, ys.min()!, ys.max()!)
}

while let path = readLine() {
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("none"); continue }
    let rect = VNDetectFaceRectanglesRequest()          // revision 3: continuous yaw / pitch / roll
    if #available(macOS 12.0, *) { rect.revision = VNDetectFaceRectanglesRequestRevision3 }
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    try? handler.perform([rect])
    guard let face = (rect.results ?? []).max(by: { $0.boundingBox.width * $0.boundingBox.height < $1.boundingBox.width * $1.boundingBox.height }) else { print("none"); continue }
    let req = VNDetectFaceLandmarksRequest()
    req.inputFaceObservations = [face]
    try? handler.perform([req])
    let f = (req.results ?? []).first ?? face
    let deg = { (n: NSNumber?) -> Double in (n?.doubleValue ?? 0) * 180 / Double.pi }
    var pitch = 0.0
    if #available(macOS 12.0, *) { pitch = deg(face.pitch) }
    var open: [Double] = [], down: [Double] = []
    let lm = f.landmarks
    for (eye, pupil) in [(lm?.leftEye, lm?.leftPupil), (lm?.rightEye, lm?.rightPupil)] {
        guard let b = box(eye) else { continue }
        let w = b.1 - b.0, h = b.3 - b.2
        if w > 0 { open.append(Double(h / w)) }
        if let pp = pupil?.normalizedPoints.first, h > 0 { down.append(Double(((b.2 + b.3) / 2 - pp.y) / h)) }
    }
    let mean = { (v: [Double]) -> Double in v.isEmpty ? -1 : v.reduce(0, +) / Double(v.count) }
    print(String(format: "%.2f %.2f %.2f %.3f %.3f", deg(face.yaw), pitch, deg(face.roll), mean(open), mean(down)))
}
