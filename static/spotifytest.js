/*
trying it in js
*/

function dewit()    {
    $.get("https://api.spotify.com/v1/albums/104", function response(data, status)  {
        document.getElementById("stuff").innerHTML = "hahahaha";
    });
};