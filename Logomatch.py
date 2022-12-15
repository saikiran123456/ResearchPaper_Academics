import cv2 as cv
import os
import sys, traceback
import numpy as np
import re 


detector = cv.xfeatures2d.SIFT_create()
doc_desc_dict = {}
cnt = 0
logo_parent_dir = r'C:\Users\Aakash\Desktop\logo_db'
logo_desc_dict = {}
cnt1 = 0
FLANN_INDEX_KDITREE=0
flannParam=dict(algorithm=FLANN_INDEX_KDITREE,tree=5)
search_params = dict(checks = 50)
flann = cv.FlannBasedMatcher(flannParam, search_params)
match_keys = {}
final_matches = {}
output_dir = r'C:\Users\Aakash\Desktop\opimg'
q = []
m=[]
logo_desc_dict = {}
cnt = 0
logo_match_dict = {}
e = r''


for logo_file in os.listdir(logo_parent_dir):
    if logo_file.endswith(".png") or logo_file.endswith(".jpg") or logo_file.endswith(".jpeg"):
        try:
            queryImg = cv.imread(os.path.join(logo_parent_dir, logo_file))
            queryImg = cv.cvtColor(queryImg, cv.COLOR_BGR2GRAY)
            logo_desc_dict[logo_file.lower()] = detector.detectAndCompute(queryImg,None)
        except:
            cnt+=1
            traceback.print_exc(file=sys.stdout)
    else:
        print(logo_file)

def getDoc(e) :
    trainImg = cv.imread(e)
    trainImg = cv.cvtColor(trainImg, cv.COLOR_BGR2GRAY)
    e = re.split('\\\\',e)
    m = e.pop()
    e = "\\".join(e)
    doc_desc_dict[m] = detector.detectAndCompute(trainImg,None)
    return e

#doc_desc_dict = getDoc()

def compute_matches(des1, des2):
    matches = flann.knnMatch(des1,des2, k=2)
    matches = sorted(matches, key = lambda x: (x[0].distance, x[1].distance))
    # Throw away 50% matches which are at a higher distance then the initial points.
    # Alternatively we can throw away higher 75% percentile of the min max distance range.
    # OR We can use X times the min distance e.g.: 3 * (min_distance)
    #threshold_distance = round(len(matches)*0.5)
    #matches = matches[:threshold_distance]
    return matches



def get_Match_Keys(doc_desc_dict, logo_desc_dict) :
    for doc_filename, doc_desc in doc_desc_dict.items():
        match_keys[doc_filename] = {k : compute_matches(v[1], doc_desc[1]) for k,v in logo_desc_dict.items()}
        
def get_Logo_Match_Dict(match_keys) :
    for doc_filename, logo_match_dict in match_keys.items():
        for k,v in logo_match_dict.items():
            goodMatch = []
            for m,n in v:
                if(m.distance<0.75*n.distance):
                    goodMatch.append(m)
            logo_match_dict[k] = goodMatch
        
def abs_ratio(a, b):
    return float(a) / b if a > b else float(b) / a



def get_good_keys(match_keys):
    for doc_filename, logo_match_dict in match_keys.items():
        match_keys[doc_filename] = {k : v for k,v in logo_match_dict.items() if len(v) >= 8}
    

def compute_homographies(k, doc_filename):
    #print(k)
    queryKP = logo_desc_dict[k][0]
    query_img = cv.imread(os.path.join(logo_parent_dir, k), 0)
    logoMatch = match_keys[doc_filename][k]

    # Read the doc params
    trainKP = doc_desc_dict[doc_filename][0]

    # collect the query and train pts
    src_pts = np.float32([ queryKP[m.queryIdx].pt for m in logoMatch ]).reshape(-1,1,2)
    dst_pts = np.float32([ trainKP[m.trainIdx].pt for m in logoMatch ]).reshape(-1,1,2)

    M, mask = cv.findHomography(src_pts, dst_pts, cv.RANSAC, 3.0) # to be fair; 3.0 sounds ok.
    matchesMask = mask.ravel().tolist()
    h,w = query_img.shape
    pts = np.float32([ [0,0],[0,h-1],[w-1,h-1],[w-1,0] ]).reshape(-1,1,2)
    dst = cv.perspectiveTransform(pts,M)
    return (pts, dst, matchesMask, M)

def get_border_penalty(k, doc_filename, matchesMask):
    num_pts_border = 0
    masked_points = [val.trainIdx for idx, val in enumerate(match_keys[doc_filename][k]) if matchesMask[idx] == 1]
    train_kps = [doc_desc_dict[doc_filename][0][mask_idx].pt for mask_idx in masked_points]
    for pt in train_kps:
        if 0 <= pt[0] <= 10 or 0 <= pt[1] <= 10:
            num_pts_border += 1
    return num_pts_border


def logo_passes_heuristic_checks(pts, dst, prev_homography_points, prev_best_area_factor, matchesMask, M, border_penalty):
    x,y,w,h = cv.boundingRect(pts)
    x1,y1,w1,h1 = cv.boundingRect(dst)
    area_factor = abs_ratio(w*h, w1*h1)
    match_count = sum(matchesMask) - border_penalty
    
    det_val = np.linalg.det(M[0:2, 0:2])
    
    src_aspect_ratio = abs_ratio(w,h)
    dst_aspect_ratio = abs_ratio(w1, h1)
    final_asp_ratio = src_aspect_ratio / dst_aspect_ratio
    
    #print(area_factor, match_count, final_asp_ratio, det_val, border_penalty)
    if area_factor < 25 and match_count >= prev_homography_points and 0.5 <= final_asp_ratio <= 1.5 and match_count >= 6 and -0.05 < det_val <= 5 and w1 > 2 and h1 > 2:
        if match_count == prev_homography_points and area_factor < prev_best_area_factor:
            #print("matched-----------------")
            return True
        elif match_count > prev_homography_points:
            #print("matched-----------------")
            return True
    else:
        return False
    

def homography_Test(final_matches) :
    for doc_filename, filtered_dict in match_keys.items():
        homography_points = 0
        prev_best_area_factor = 0
        for k,v in filtered_dict.items():
            try:
                pts, dst, matchesMask, M = compute_homographies(k, doc_filename)
                border_penalty = get_border_penalty(k, doc_filename, matchesMask)
                if logo_passes_heuristic_checks(pts, dst, homography_points, prev_best_area_factor, matchesMask, M, border_penalty):
                    homography_points = sum(matchesMask) - border_penalty
                    x,y,w,h = cv.boundingRect(pts)
                    x1,y1,w1,h1 = cv.boundingRect(dst)
                    prev_best_area_factor = abs_ratio(w*h, w1*h1)  
                    final_matches[doc_filename] = [k, matchesMask, M]
            except:
                pass
            #print("No Homography Transformation for", doc_filename, k)
            #traceback.print_exc(file=sys.stdout)


def op(final_matches,logo_parent_dir , e , doc_desc_dict , match_keys , logo_desc_dict , output_dir) :
    for doc_filename,v in final_matches.items():
        try:
            val_filename = v[0]
            validation_img = cv.imread(os.path.join(logo_parent_dir, val_filename), 0)
            train_img = cv.imread(os.path.join(e, val_filename), 0)
            trainKP = doc_desc_dict[doc_filename][0]
            true_match = match_keys[doc_filename][val_filename]
            draw_params = dict(matchColor = (0,255,0), # draw matches in green color
                               singlePointColor = None,
                               matchesMask = v[1], # draw only inliers
                               flags = 2)
            
            out_img = cv.drawMatches(validation_img,logo_desc_dict[val_filename][0],train_img,trainKP,true_match,None,flags=2)
            cv.imwrite(os.path.join(output_dir, doc_filename), out_img)
            cv.destroyAllWindows()
        except:
            print('1')
    return val_filename
      
def implement(l) :
    e = getDoc(l)
    get_Match_Keys(doc_desc_dict , logo_desc_dict)
    get_Logo_Match_Dict(match_keys)
    get_good_keys(match_keys)
    homography_Test(final_matches)
    p = op(final_matches,logo_parent_dir , e , doc_desc_dict , match_keys ,logo_desc_dict , output_dir)
    return p