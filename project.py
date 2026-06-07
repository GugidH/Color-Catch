import os
import sys
import math
import random
import time
import tkinter as tk
from tkinter import filedialog
import cv2 as cv
import numpy as np
import pygame

# ----------------------------------------------------
# 시스템 초기화 및 해상도 세팅
# ----------------------------------------------------
pygame.init()
pygame.font.init()

WIDTH, HEIGHT = 1200, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Color Hunter: Switch! (Everybody 1-2-Switch! Tribute)")
clock = pygame.time.Clock()

# 테마 디자인 컬러 에셋 (RGB)
BLACK = (15, 15, 15)
WHITE = (245, 245, 245)
GRAY = (60, 60, 60)
LIGHT_GRAY = (180, 180, 180)
GOLD = (255, 215, 0)
RED = (255, 90, 90)
GREEN = (90, 255, 90)
BLUE = (52, 152, 219)

def get_font(size):
    font_names = ["malgungothic", "applesgothicneo", "nanumgothic", "arial"]
    for name in font_names:
        try:
            return pygame.font.SysFont(name, size)
        except:
            continue
    return pygame.font.Font(None, size)

FONT_BIG = get_font(52)
FONT_MID = get_font(28)
FONT_SMALL = get_font(18)

# ----------------------------------------------------
# 색상 생성 알고리즘
# ----------------------------------------------------
def generate_vibrant_random_color(existing_colors=[]):

    BASE_POOL = [
        (230, 60, 60),  
        (40, 140, 220),  
        (40, 200, 100),  
        (240, 190, 15), 
        (150, 80, 180),  
        (230, 120, 30), 
        (20, 180, 150)   
    ]
    
    # 이전에 선점된 베이스 구역을 제외하고 후보군 추출
    available_bases = []
    for base in BASE_POOL:
        is_used = False
        for ext in existing_colors:
            # 기존에 뽑힌 색상이 이 베이스 구역에서 파생된 색상인지 거리 측정
            dist = math.sqrt((base[0]-ext[0])**2 + (base[1]-ext[1])**2 + (base[2]-ext[2])**2)
            if dist < 65:  # 파생 영역 바운더리 내에 있다면 이미 사용된 구역으로 판정
                is_used = True
                break
        if not is_used:
            available_bases.append(base)
            
    # 만약 후보군이 다 떨어지면 전체 풀에서 무작위 선택
    selected_base = random.choice(available_bases) if available_bases else random.choice(BASE_POOL)
    
    # 선택된 베이스 색상에서 RGB 값을 약간 비틀어 변주
    r_mut = max(30, min(245, selected_base[0] + random.randint(-25, 25)))
    g_mut = max(30, min(245, selected_base[1] + random.randint(-25, 25)))
    b_mut = max(30, min(245, selected_base[2] + random.randint(-25, 25)))
    
    return (r_mut, g_mut, b_mut)

# ----------------------------------------------------
# 비전 매칭 알고리즘
# ----------------------------------------------------
def calculate_color_match_from_surface(target_rgb, pygame_surface):
    """
    Gaussian distribution 곡선을 스코어링 커브에 직접 적용하여,
    극단적인 점수를 줄이고 중간 대역에 점수가 모이도록 조율한 정규분포형 알고리즘
    """
    try:
        view = pygame.surfarray.array3d(pygame_surface)
        img_rgb = np.transpose(view, (1, 0, 2))
        
        # ROI 지정 - 핵심 중앙 50% 영역 크롭
        h, w, _ = img_rgb.shape
        cy, cx = h // 2, w // 2
        dy, dx = int(h * 0.25), int(w * 0.25)
        roi_rgb = img_rgb[cy-dy:cy+dy, cx-dx:cx+dx]
        
        # Smoothing - 가우시안 블러 필터링
        roi_blur = cv.GaussianBlur(roi_rgb, (11, 11), 0)
        
        # Color Space Conversion - RGB to HSV
        hsv_roi = cv.cvtColor(roi_blur, cv.COLOR_RGB2HSV)
        
        target_rgb_img = np.uint8([[[target_rgb[0], target_rgb[1], target_rgb[2]]]])
        target_hsv = cv.cvtColor(target_rgb_img, cv.COLOR_RGB2HSV)[0][0]
        
        h_channel = hsv_roi[:, :, 0].flatten()
        s_channel = hsv_roi[:, :, 1].flatten()
        v_channel = hsv_roi[:, :, 2].flatten()
        
        valid_pixels = (s_channel > 20) & (v_channel > 20)
        if np.sum(valid_pixels) > 0:
            pred_h = np.median(h_channel[valid_pixels])
            pred_s = np.median(s_channel[valid_pixels])
            pred_v = np.median(v_channel[valid_pixels])
        else:
            pred_h = np.median(h_channel)
            pred_s = np.median(s_channel)
            pred_v = np.median(v_channel)
            
        # Hue의 원형 180도 각도 거리 산출
        hue_diff = abs(pred_h - target_hsv[0])
        hue_distance = min(hue_diff, 180 - hue_diff)
        
        sat_distance = abs(pred_s - target_hsv[1])
        val_distance = abs(pred_v - target_hsv[2])
        
        # 3차원 유클리드 가중치 공간 거리 계산
        total_distance = math.sqrt((hue_distance * 3.0) ** 2 + (sat_distance * 0.4) ** 2 + (val_distance * 0.2) ** 2)
        
        # 공식: exp(- (distance^2) / (2 * sigma^2)) * 100 만점
        # 표준편차(sigma=42.0)를 통해 종 모양 곡선의 완만함을 제어하여 중간 점수대 쏠림 현상을 구현
        sigma = 42.0  
        gaussian_score = math.exp(- (total_distance ** 2) / (2 * (sigma ** 2))) * 100
        
        # 최종 백분율 인트형 맵핑
        match_percentage = max(0, min(100, int(gaussian_score)))
            
        return match_percentage
    except Exception as e:
        print(f"비전 알고리즘 오류: {e}")
        return 0

# ----------------------------------------------------
# 그래픽 물리 입자 및 엔티티 클래스 정의
# ----------------------------------------------------
class FireworksParticle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(3, 9)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.radius = random.randint(3, 6)
        self.alpha = 255

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.12
        self.alpha -= 3

    def draw(self, surface):
        if self.alpha > 0:
            p_surf = pygame.Surface((self.radius*2, self.radius*2), pygame.SRCALPHA)
            pygame.draw.circle(p_surf, (*self.color, self.alpha), (self.radius, self.radius), self.radius)
            surface.blit(p_surf, (int(self.x - self.radius), int(self.y - self.radius)))

class GamePlayer:
    def __init__(self, p_id):
        self.id = p_id
        self.total_score = 0
        self.current_match = 0
        self.display_match = 0.0
        self.image_path = None
        self.uploaded_texture = None
        self.is_winner_this_round = False
        self.bonus_points = 0
        self.highest_match_percentage = -1
        self.highest_match_image = None
        self.highest_match_target_color = (0, 0, 0)

# ----------------------------------------------------
# 전체 시나리오 상태 머신 제어 루프
# ----------------------------------------------------
def main():
    root = tk.Tk()
    root.withdraw()

    STAGE_INTRO = 0
    STAGE_SHOW_COLOR = 1
    STAGE_UPLOAD = 2
    STAGE_COUNT_UP = 3
    STAGE_SHOW_WINNER = 4
    STAGE_GAME_OVER = 5
    
    current_stage = STAGE_INTRO
    num_players = 2
    players = []
    
    current_round = 0
    stage_timer = 0
    particles = []
    round_colors = []
    for _ in range(5):
        round_colors.append(generate_vibrant_random_color(round_colors))

    
    running = True
    while running:
        screen.fill(BLACK)
        dt = clock.tick(60)
        mx, my = pygame.mouse.get_pos()
        
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
                
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if current_stage == STAGE_INTRO:
                    if 250 <= mx <= 400 and 450 <= my <= 510:
                        num_players = max(1, num_players - 1)
                    elif 550 <= mx <= 700 and 450 <= my <= 510:
                        num_players = min(4, num_players + 1)
                    elif 450 <= mx <= 750 and 580 <= my <= 660:
                        players = [GamePlayer(i+1) for i in range(num_players)]
                        current_round = 0
                     
                        round_colors = [generate_vibrant_random_color() for _ in range(5)]
                        
                        stage_timer = pygame.time.get_ticks()
                        current_stage = STAGE_SHOW_COLOR
                        
                elif current_stage == STAGE_UPLOAD:
                    lane_w = WIDTH / num_players
                    for i, p in enumerate(players):
                        x_start = i * lane_w
                        if x_start <= mx <= x_start + lane_w and 120 <= my <= HEIGHT:
                            file_path = filedialog.askopenfilename(
                                filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.webp")]
                            )
                            if file_path:
                                p.image_path = file_path
                                try:
                                    img_surf = pygame.image.load(file_path)
                                    p.uploaded_texture = pygame.transform.scale(img_surf, (220, 220))
                                except:
                                    print("이미지 에러.")
                                    
                elif current_stage == STAGE_GAME_OVER:
                    if WIDTH//2 - 150 <= mx <= WIDTH//2 + 150 and 700 <= my <= 765:
                        current_stage = STAGE_INTRO
                        num_players = 2
                        players = []
                        current_round = 0
                        particles = []
                        round_colors = []
        
        # STAGE 0: 오프닝
        if current_stage == STAGE_INTRO:
            title_text = FONT_BIG.render("Coler Catch", True, GOLD)
            screen.blit(title_text, (WIDTH // 2 - title_text.get_width() // 2, 140))
            
            players_text = FONT_BIG.render(f"참여 플레이어 수: {num_players} 명", True, WHITE)
            screen.blit(players_text, (WIDTH // 2 - players_text.get_width() // 2, 340))
            
            pygame.draw.rect(screen, GRAY, (250, 450, 150, 60), border_radius=8)
            minus_txt = FONT_MID.render("- 1명", True, WHITE)
            screen.blit(minus_txt, (325 - minus_txt.get_width()//2, 465))
            
            pygame.draw.rect(screen, GRAY, (550, 450, 150, 60), border_radius=8)
            plus_txt = FONT_MID.render("+ 1명", True, WHITE)
            screen.blit(plus_txt, (625 - plus_txt.get_width()//2, 465))
            
            pygame.draw.rect(screen, GOLD, (450, 580, 300, 80), border_radius=12)
            start_txt = FONT_MID.render("START", True, BLACK)
            screen.blit(start_txt, (600 - start_txt.get_width()//2, 605))

        # STAGE 1: 무작위 컬러 연동 5초 타임라인 씬
        elif current_stage == STAGE_SHOW_COLOR:
            elapsed = (pygame.time.get_ticks() - stage_timer) / 1000
            remaining_int = max(0, math.ceil(5.0 - elapsed))
            
            round_txt = FONT_BIG.render(f"ROUND {current_round + 1} / 5", True, GOLD)
            screen.blit(round_txt, (WIDTH//2 - round_txt.get_width()//2, 40))
            
            guide_txt = FONT_MID.render("방 안에서 아래의 색상과 가장 똑같은 사물을 찾으세요!", True, WHITE)
            screen.blit(guide_txt, (WIDTH//2 - guide_txt.get_width()//2, 110))
            
            target_color = round_colors[current_round]
            pygame.draw.rect(screen, target_color, (WIDTH//2 - 160, 200, 320, 320), border_radius=20)
            pygame.draw.rect(screen, WHITE, (WIDTH//2 - 160, 200, 320, 320), 5, border_radius=20)
            
            timer_txt = FONT_BIG.render(f"탐색 제한 시간: {remaining_int}초", True, RED)
            screen.blit(timer_txt, (WIDTH//2 - timer_txt.get_width()//2, 590))
            
            if remaining_int <= 0:
                current_stage = STAGE_UPLOAD
                for p in players:
                    p.image_path = None
                    p.uploaded_texture = None
                    p.current_match = 0
                    p.display_match = 0.0
                    p.is_winner_this_round = False
                    p.bonus_points = 0

        # STAGE 2: 업로드 수신 레이아웃 구역
        elif current_stage == STAGE_UPLOAD:
            lane_w = WIDTH / num_players
            target_color = round_colors[current_round]
            
            pygame.draw.rect(screen, target_color, (25, 20, 50, 50), border_radius=8)
            pygame.draw.rect(screen, WHITE, (25, 20, 50, 50), 2, border_radius=8)
            info_txt = FONT_MID.render(f"라운드 {current_round+1} 미션 - 자신의 칸을 마우스로 클릭해 사진을 업로드하세요.", True, WHITE)
            screen.blit(info_txt, (95, 30))
            
            all_uploaded = True
            for i, p in enumerate(players):
                x_start = i * lane_w
                if x_start <= mx <= x_start + lane_w and 120 <= my <= HEIGHT:
                    pygame.draw.rect(screen, (35, 35, 35), (x_start + 4, 110, lane_w - 8, HEIGHT - 120), border_radius=10)
                
                if i > 0:
                    pygame.draw.line(screen, GRAY, (x_start, 110), (x_start, HEIGHT), 2)
                
                p_title = FONT_MID.render(f"플레이어 {p.id}", True, GOLD)
                screen.blit(p_title, (x_start + lane_w//2 - p_title.get_width()//2, 140))
                
                if p.uploaded_texture:
                    screen.blit(p.uploaded_texture, (x_start + (lane_w - 220)//2, 260))
                    ready_txt = FONT_MID.render("준비 완료! (Ready)", True, GREEN)
                    screen.blit(ready_txt, (x_start + lane_w//2 - ready_txt.get_width()//2, 530))
                else:
                    all_uploaded = False
                    pygame.draw.rect(screen, (25, 25, 25), (x_start + (lane_w - 220)//2, 260, 220, 220), border_radius=10)
                    pygame.draw.rect(screen, GRAY, (x_start + (lane_w - 220)//2, 260, 220, 220), 2, border_radius=10)
                    click_txt = FONT_MID.render("클릭하여 업로드", True, LIGHT_GRAY)
                    screen.blit(click_txt, (x_start + lane_w//2 - click_txt.get_width()//2, 355))
            
            if all_uploaded:
                for p in players:
                    p.current_match = calculate_color_match_from_surface(target_color, p.uploaded_texture)
                    if p.current_match > p.highest_match_percentage:
                        p.highest_match_percentage = p.current_match
                        p.highest_match_image = p.uploaded_texture
                        p.highest_match_target_color = target_color
                
                max_score = max(p.current_match for p in players)
                for p in players:
                    if p.current_match == max_score and max_score > 0:
                        p.is_winner_this_round = True
                        p.bonus_points = 10 if num_players > 1 else 0
                
                current_stage = STAGE_COUNT_UP

        # STAGE 3: 점수 카운트업
        elif current_stage == STAGE_COUNT_UP:
            lane_w = WIDTH / num_players
            all_count_finished = True
            
            for i, p in enumerate(players):
                x_start = i * lane_w
                if i > 0:
                    pygame.draw.line(screen, GRAY, (x_start, 110), (x_start, HEIGHT), 2)
                
                p_title = FONT_MID.render(f"플레이어 {p.id}", True, GOLD)
                screen.blit(p_title, (x_start + lane_w//2 - p_title.get_width()//2, 140))
                if p.uploaded_texture:
                    screen.blit(p.uploaded_texture, (x_start + (lane_w - 220)//2, 260))
                
                if p.display_match < p.current_match:
                    p.display_match += 0.8
                    if p.display_match > p.current_match:
                        p.display_match = p.current_match
                    all_count_finished = False
                
                score_txt = FONT_BIG.render(f"{int(p.display_match)} %", True, WHITE)
                screen.blit(score_txt, (x_start + lane_w//2 - score_txt.get_width()//2, 520))
            
            if all_count_finished:
                stage_timer = pygame.time.get_ticks()
                current_stage = STAGE_SHOW_WINNER
                
                if num_players > 1:
                    for i, p in enumerate(players):
                        if p.is_winner_this_round:
                            x_center = int(i * lane_w + lane_w // 2)
                            for _ in range(120):
                                particles.append(FireworksParticle(x_center, 380, random.choice([GOLD, RED, GREEN, BLUE, WHITE])))

        # STAGE 4: 5초 대기 및 세레머니
        elif current_stage == STAGE_SHOW_WINNER:
            lane_w = WIDTH / num_players
            elapsed = (pygame.time.get_ticks() - stage_timer) / 1000
            remaining_wait_int = max(0, math.ceil(5.0 - elapsed))
            
            for pt in particles[:]:
                pt.update()
                pt.draw(screen)
                if pt.alpha <= 0:
                    particles.remove(pt)
            
            for i, p in enumerate(players):
                x_start = i * lane_w
                if i > 0:
                    pygame.draw.line(screen, GRAY, (x_start, 110), (x_start, HEIGHT), 2)
                
                if num_players > 1 and p.is_winner_this_round:
                    pygame.draw.rect(screen, GOLD, (x_start + 6, 115, lane_w - 12, HEIGHT - 135), 6, border_radius=12)
                    bonus_txt = FONT_MID.render("보너스 점수 +10!", True, GOLD)
                    screen.blit(bonus_txt, (x_start + lane_w//2 - bonus_txt.get_width()//2, 640))
                
                p_title = FONT_MID.render(f"플레이어 {p.id}" if num_players > 1 else "SCORE", True, GOLD)
                screen.blit(p_title, (x_start + lane_w//2 - p_title.get_width()//2, 140))
                if p.uploaded_texture:
                    screen.blit(p.uploaded_texture, (x_start + (lane_w - 220)//2, 260))
                
                score_txt = FONT_BIG.render(f"{p.current_match} %", True, WHITE)
                screen.blit(score_txt, (x_start + lane_w//2 - score_txt.get_width()//2, 520))
                
                earned_points = p.current_match + p.bonus_points if num_players > 1 else p.current_match
                round_score_txt = FONT_MID.render(f"+ {earned_points} 점", True, GREEN)
                high_offset = 590 if num_players > 1 else 610
                screen.blit(round_score_txt, (x_start + lane_w//2 - round_score_txt.get_width()//2, high_offset))
            
            next_timer_txt = FONT_MID.render(f"{remaining_wait_int}초 후 다음 라운드로 화면이 자동 리셋됩니다.", True, LIGHT_GRAY)
            screen.blit(next_timer_txt, (WIDTH//2 - next_timer_txt.get_width()//2, 35))
            
            if remaining_wait_int <= 0:
                for p in players:
                    p.total_score += (p.current_match + p.bonus_points) if num_players > 1 else p.current_match
                
                current_round += 1
                if current_round >= 5:
                    current_stage = STAGE_GAME_OVER
                else:
                    stage_timer = pygame.time.get_ticks()
                    current_stage = STAGE_SHOW_COLOR

        # STAGE 5: 최종 정산
        elif current_stage == STAGE_GAME_OVER:
            over_title = "최종 점수 결과" if num_players == 1 else "최종 랭킹"
            over_txt = FONT_BIG.render(over_title, True, GOLD)
            screen.blit(over_txt, (WIDTH//2 - over_txt.get_width()//2, 40))
            
            lane_w = WIDTH / num_players
            max_final_score = max(p.total_score for p in players)
            
            for i, p in enumerate(players):
                x_start = i * lane_w
                if i > 0:
                    pygame.draw.line(screen, GRAY, (x_start, 130), (x_start, HEIGHT), 2)
                
                if num_players > 1:
                    if p.total_score == max_final_score:
                        pygame.draw.rect(screen, GOLD, (x_start + 6, 135, lane_w - 12, HEIGHT - 180), 4, border_radius=12)
                        crown_txt = FONT_MID.render("WINNER", True, GOLD)
                        screen.blit(crown_txt, (x_start + lane_w//2 - crown_txt.get_width()//2, 155))
                    p_title = FONT_MID.render(f"플레이어 {p.id}", True, WHITE)
                else:
                    p_title = FONT_MID.render("FINAL SCORE", True, WHITE)
                
                screen.blit(p_title, (x_start + lane_w//2 - p_title.get_width()//2, 210))
                
                total_txt = FONT_BIG.render(f"{p.total_score} 점", True, GREEN)
                screen.blit(total_txt, (x_start + lane_w//2 - total_txt.get_width()//2, 260))
                
                best_label = FONT_MID.render(f"HIGHLIGHT ({p.highest_match_percentage}%)", True, GOLD)
                screen.blit(best_label, (x_start + lane_w//2 - best_label.get_width()//2, 360))
                
                if p.highest_match_image:
                    # 사물 사진 중심 배치
                    img_x = x_start + (lane_w - 220) // 2
                    img_y = 420
                    screen.blit(p.highest_match_image, (img_x, img_y))
                    
                    col_box_txt = FONT_SMALL.render("당시 미션 색상", True, LIGHT_GRAY)
                    screen.blit(col_box_txt, (img_x, img_y + 235))
                    
                    pygame.draw.rect(screen, p.highest_match_target_color, (img_x + 130, img_y + 233, 90, 24), border_radius=4)
                    pygame.draw.rect(screen, WHITE, (img_x + 130, img_y + 233, 90, 24), 2, border_radius=4)
            
            # 리셋 버튼
            pygame.draw.rect(screen, GOLD, (WIDTH//2 - 150, 700, 300, 65), border_radius=10)
            btn_play_again_txt = FONT_MID.render("새 게임 시작 (Reset)", True, BLACK)
            screen.blit(btn_play_again_txt, (WIDTH//2 - btn_play_again_txt.get_width()//2, 715))
                    
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()