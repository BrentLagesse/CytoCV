      // CSRF helper
      function getCookie(name) {
        let val = null;
        document.cookie.split(";").forEach((c) => {
          c = c.trim();
          if (c.startsWith(name + "=")) {
            val = decodeURIComponent(c.slice(name.length + 1));
          }
        });
        return val;
      }

      // Make each .channel-bar sortable
      document.querySelectorAll(".channel-bar").forEach((bar) => {
        const uuid = bar.parentElement.dataset.uuid;
        Sortable.create(bar, {
          animation: 150,
          onEnd() {
            const newOrder = Array.from(bar.children).map((chip) => (
              chip.dataset.channelLabel ||
              chip.querySelector(".channel-chip-label")?.textContent?.trim() ||
              chip.textContent.trim()
            ));
            fetch(`/api/update-channel-order/${uuid}/`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
              },
              body: JSON.stringify({ order: newOrder }),
            }).then((r) => {
              if (!r.ok) console.error("Failed to save channel order", r);
            });
          },
        });
      });
