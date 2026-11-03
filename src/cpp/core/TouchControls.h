#ifndef CORE_TOUCHCONTROLS_H
#define CORE_TOUCHCONTROLS_H

// Kontrol sentuh (Android):
//   Ketuk            -> klik kiri (pilih / konfirmasi)
//   Tahan ~0,4 detik -> klik kanan (perintah)
//   Geser 1 jari     -> geser kamera
//   Tombol di layar  -> pintasan keyboard (ESC, putar bangunan, garrison, menu bangun, dst.)
//
// Event sentuh dibaca di thread render (SDL_PollEvent di Renderer), lalu diubah menjadi
// Event::MOUSE_* / Event::KEY_* dan dimasukkan ke antrean. InputProcessor (thread event loop)
// mengosongkan antrean itu sehingga seluruh game memakai jalur input yang sama seperti mouse.

#include "Event.h"

#include <SDL3/SDL.h>
#include <algorithm>
#include <cmath>
#include <deque>
#include <mutex>

namespace core
{
class TouchControls
{
  public:
    static TouchControls& instance()
    {
        static TouchControls inst;
        return inst;
    }

    // Dipanggil dari thread event loop.
    template <typename Callback> void drain(const Callback& callback)
    {
        std::deque<Event> local;
        {
            std::lock_guard<std::mutex> lock(m_mutex);
            local.swap(m_queue);
        }
        for (const auto& e : local)
            callback(e);
    }

    // ---- Semua fungsi di bawah dipanggil dari thread render ----

    void onSdlEvent(const SDL_Event& ev, SDL_Window* window, SDL_Renderer* renderer)
    {
        switch (ev.type)
        {
        case SDL_EVENT_FINGER_DOWN:
        {
            float x = 0, y = 0;
            toRender(ev.tfinger.x, ev.tfinger.y, window, renderer, x, y);
            ++m_fingersDown;
            if (m_fingersDown > 1)
            {
                // Dua jari: dicadangkan untuk cubit-zoom nanti. Batalkan ketuk/geser.
                m_state = State::IGNORED;
                break;
            }
            m_finger = ev.tfinger.fingerID;
            const int b = hitButton(x, y);
            if (b >= 0)
            {
                m_state = State::BUTTON;
                m_button = b;
                break;
            }
            m_state = State::PRESSED;
            m_startX = m_lastX = x;
            m_startY = m_lastY = y;
            m_downMs = SDL_GetTicks();
            break;
        }
        case SDL_EVENT_FINGER_MOTION:
        {
            if (m_fingersDown != 1 || ev.tfinger.fingerID != m_finger)
                break;
            float x = 0, y = 0;
            toRender(ev.tfinger.x, ev.tfinger.y, window, renderer, x, y);
            if (m_state == State::PRESSED)
            {
                const float dx = x - m_startX;
                const float dy = y - m_startY;
                const float threshold = std::max(10.0f, m_viewH * 0.015f);
                if (dx * dx + dy * dy > threshold * threshold)
                {
                    m_state = State::PANNING;
                    m_lastX = x;
                    m_lastY = y;
                }
            }
            else if (m_state == State::PANNING)
            {
                m_panX += x - m_lastX;
                m_panY += y - m_lastY;
                m_lastX = x;
                m_lastY = y;
            }
            break;
        }
        case SDL_EVENT_FINGER_UP:
        case SDL_EVENT_FINGER_CANCELED:
        {
            float x = 0, y = 0;
            toRender(ev.tfinger.x, ev.tfinger.y, window, renderer, x, y);
            if (m_fingersDown > 0)
                --m_fingersDown;
            if (m_fingersDown == 0)
            {
                const bool released = ev.type == SDL_EVENT_FINGER_UP;
                if (released && m_state == State::PRESSED)
                {
                    pushClick(MouseClickData::Button::LEFT, x, y);
                }
                else if (released && m_state == State::BUTTON && hitButton(x, y) == m_button)
                {
                    pressButton(m_button);
                }
                m_state = State::IDLE;
                m_button = -1;
            }
            break;
        }
        default:
            break;
        }
    }

    // Tahan lama -> klik kanan. Dipanggil sekali per frame.
    void update()
    {
        if (m_state == State::PRESSED && SDL_GetTicks() - m_downMs >= HOLD_MS)
        {
            pushClick(MouseClickData::Button::RIGHT, m_startX, m_startY);
            m_state = State::HOLD_DONE;
        }
    }

    // Selisih geser (piksel layar) sejak panggilan terakhir. Kamera = posisi kamera - selisih.
    Vec2 takePan()
    {
        const int ix = static_cast<int>(std::trunc(m_panX));
        const int iy = static_cast<int>(std::trunc(m_panY));
        m_panX -= static_cast<float>(ix);
        m_panY -= static_cast<float>(iy);
        return Vec2(ix, iy);
    }

    void draw(SDL_Renderer* r)
    {
        if (!refreshView(r))
            return;

        SDL_BlendMode oldMode = SDL_BLENDMODE_NONE;
        SDL_GetRenderDrawBlendMode(r, &oldMode);
        Uint8 oldR = 0, oldG = 0, oldB = 0, oldA = 255;
        SDL_GetRenderDrawColor(r, &oldR, &oldG, &oldB, &oldA);
        float oldSx = 1, oldSy = 1;
        SDL_GetRenderScale(r, &oldSx, &oldSy);

        SDL_SetRenderDrawBlendMode(r, SDL_BLENDMODE_BLEND);

        const int count = visibleCount();
        const float k = std::max(1.0f, std::floor(buttonSize() / 32.0f));
        for (int i = 0; i < count; ++i)
        {
            const SDL_FRect rect = buttonRect(i);
            const bool pressed = (m_state == State::BUTTON && m_button == i);
            SDL_SetRenderDrawColor(r, pressed ? 200 : 20, pressed ? 170 : 20, pressed ? 60 : 20,
                                   190);
            SDL_RenderFillRect(r, &rect);
            SDL_SetRenderDrawColor(r, 230, 230, 230, 255);
            SDL_RenderRect(r, &rect);

            const char* label = labelOf(i);
            const float textW = 8.0f * k * static_cast<float>(SDL_strlen(label));
            const float tx = rect.x + (rect.w - textW) / 2;
            const float ty = rect.y + (rect.h - 8.0f * k) / 2;
            SDL_SetRenderScale(r, oldSx * k, oldSy * k);
            SDL_RenderDebugText(r, tx / k, ty / k, label);
            SDL_SetRenderScale(r, oldSx, oldSy);
        }

        SDL_SetRenderDrawBlendMode(r, oldMode);
        SDL_SetRenderDrawColor(r, oldR, oldG, oldB, oldA);
    }

  private:
    enum class State
    {
        IDLE,
        PRESSED,   // satu jari menyentuh, belum jelas ketuk / geser / tahan
        PANNING,   // sedang geser kamera
        HOLD_DONE, // klik kanan sudah dikirim, abaikan sisa sentuhan
        BUTTON,    // jari menekan tombol di layar
        IGNORED    // lebih dari satu jari
    };

    struct Button
    {
        const char* label;
        SDL_Scancode key;
    };

    static constexpr Uint64 HOLD_MS = 400;
    static constexpr int COLUMNS = 4;

    // Indeks tombol di layar: 0 = tombol buka/tutup, 1.. = pintasan di bawah.
    static const Button* buttons(int& n)
    {
        static const Button list[] = {
            {"ESC", SDL_SCANCODE_ESCAPE}, {"ROT", SDL_SCANCODE_LCTRL}, {"G", SDL_SCANCODE_G},
            {"U", SDL_SCANCODE_U},        {"M", SDL_SCANCODE_M},       {"L", SDL_SCANCODE_L},
            {"N", SDL_SCANCODE_N},        {"C", SDL_SCANCODE_C},       {"B", SDL_SCANCODE_B},
            {"P", SDL_SCANCODE_P},        {"O", SDL_SCANCODE_O},       {"I", SDL_SCANCODE_I},
            {"H", SDL_SCANCODE_H},        {"V", SDL_SCANCODE_V},
        };
        n = static_cast<int>(sizeof(list) / sizeof(list[0]));
        return list;
    }

    TouchControls() = default;

    void push(Event e)
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_queue.push_back(std::move(e));
    }

    void pushClick(MouseClickData::Button button, float x, float y)
    {
        const Vec2 pos(static_cast<int>(x), static_cast<int>(y));
        push(Event(Event::Type::MOUSE_MOVE, MouseMoveData{pos}));
        push(Event(Event::Type::MOUSE_BTN_DOWN, MouseClickData{button, pos}));
        push(Event(Event::Type::MOUSE_BTN_UP, MouseClickData{button, pos}));
    }

    void pushKey(SDL_Scancode key)
    {
        push(Event(Event::Type::KEY_DOWN, KeyboardData{static_cast<int>(key)}));
        push(Event(Event::Type::KEY_UP, KeyboardData{static_cast<int>(key)}));
    }

    void pressButton(int index)
    {
        if (index == 0)
        {
            m_expanded = !m_expanded;
            return;
        }
        int n = 0;
        const Button* list = buttons(n);
        if (index - 1 < n)
            pushKey(list[index - 1].key);
    }

    const char* labelOf(int index) const
    {
        if (index == 0)
            return m_expanded ? "X" : "KEY";
        int n = 0;
        const Button* list = buttons(n);
        return list[index - 1].label;
    }

    int visibleCount() const
    {
        int n = 0;
        buttons(n);
        return m_expanded ? 1 + n : 1;
    }

    float buttonSize() const
    {
        return std::max(40.0f, m_viewH * 0.08f);
    }

    SDL_FRect buttonRect(int index) const
    {
        const float s = buttonSize();
        const float gap = s * 0.12f;
        if (index == 0)
            return SDL_FRect{m_viewW - gap - s, gap, s, s};

        const int i = index - 1;
        const int col = i % COLUMNS;
        const int row = i / COLUMNS;
        const float left = m_viewW - gap - COLUMNS * s - (COLUMNS - 1) * gap;
        return SDL_FRect{left + col * (s + gap), gap + (s + gap) + row * (s + gap), s, s};
    }

    int hitButton(float x, float y) const
    {
        const int count = visibleCount();
        for (int i = 0; i < count; ++i)
        {
            const SDL_FRect r = buttonRect(i);
            if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h)
                return i;
        }
        return -1;
    }

    // Ukuran area gambar: ukuran logis kalau dipakai, kalau tidak ukuran keluaran renderer.
    bool refreshView(SDL_Renderer* r)
    {
        int w = 0, h = 0;
        SDL_RendererLogicalPresentation mode = SDL_LOGICAL_PRESENTATION_DISABLED;
        if (!SDL_GetRenderLogicalPresentation(r, &w, &h, &mode) ||
            mode == SDL_LOGICAL_PRESENTATION_DISABLED)
        {
            if (!SDL_GetCurrentRenderOutputSize(r, &w, &h))
                return false;
        }
        m_viewW = static_cast<float>(w);
        m_viewH = static_cast<float>(h);
        return w > 0 && h > 0;
    }

    // Koordinat jari (0..1) -> koordinat gambar renderer (sama dengan yang dipakai game).
    void toRender(float nx, float ny, SDL_Window* window, SDL_Renderer* r, float& x, float& y)
    {
        refreshView(r);
        int ww = 1, wh = 1;
        SDL_GetWindowSize(window, &ww, &wh);
        x = nx * static_cast<float>(ww);
        y = ny * static_cast<float>(wh);
        SDL_RenderCoordinatesFromWindow(r, x, y, &x, &y);
    }

    std::mutex m_mutex;
    std::deque<Event> m_queue;

    State m_state = State::IDLE;
    SDL_FingerID m_finger = 0;
    int m_fingersDown = 0;
    int m_button = -1;
    bool m_expanded = false;
    Uint64 m_downMs = 0;
    float m_startX = 0, m_startY = 0;
    float m_lastX = 0, m_lastY = 0;
    float m_panX = 0, m_panY = 0;
    float m_viewW = 0, m_viewH = 0;
};
} // namespace core

#endif // CORE_TOUCHCONTROLS_H
